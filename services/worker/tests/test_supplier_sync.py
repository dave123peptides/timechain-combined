from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, text

from worker import config as worker_config
from worker.alliancetek.client import AllianceTekClient, SupplierApiConfigError, SupplierApiError
from worker.config import get_settings
from worker.supplier_sync.db import upsert_supplier_products
from worker.supplier_sync.mapping import SupplierProductFieldError, map_supplier_product
from worker.supplier_sync.reconciliation import get_mapped_supplier_product_ids, reconcile_mapping_drift
from worker.supplier_sync.sync import SupplierSyncValidationError, fetch_all_supplier_products
from worker.supplier_sync import sync as sync_module

# ---------------------------------------------------------------------------
# mapping.py
# ---------------------------------------------------------------------------


def test_map_supplier_product_happy_path():
    raw = {"productId": 987654, "sku": "5AM1-50", "name": "BPC 157 5mg", "active": True, "price": 2200}
    row = map_supplier_product(raw)
    assert row["supplier_product_id"] == 987654
    assert row["supplier_sku"] == "5AM1-50"
    assert isinstance(row["supplier_sku"], str)
    assert row["supplier_name"] == "BPC 157 5mg"
    assert row["supplier_active"] is True
    assert row["supplier_price_cents"] == 2200
    assert row["raw_payload"] == raw


def test_map_supplier_product_alternate_field_names():
    raw = {"productId": 1, "productSku": "ABC-1", "productName": "Widget", "isActive": "true"}
    row = map_supplier_product(raw)
    assert row["supplier_sku"] == "ABC-1"
    assert row["supplier_name"] == "Widget"
    assert row["supplier_active"] is True
    assert row["supplier_price_cents"] is None


def test_map_supplier_product_missing_product_id_raises():
    with pytest.raises(SupplierProductFieldError):
        map_supplier_product({"sku": "X"})


def test_map_supplier_product_missing_sku_raises_with_raw_keys():
    with pytest.raises(SupplierProductFieldError) as exc_info:
        map_supplier_product({"productId": 1, "name": "Widget", "active": True})
    assert "productId=1" in str(exc_info.value)


def test_map_supplier_product_unrecognized_active_value_raises():
    with pytest.raises(SupplierProductFieldError):
        map_supplier_product({"productId": 1, "sku": "X", "name": "Y", "active": "sort-of"})


# ---------------------------------------------------------------------------
# Pagination (client.py + sync.py), using httpx.MockTransport — no network.
# ---------------------------------------------------------------------------


def _fake_page_response(page: int, pages: int, total: int, products: list[dict]) -> httpx.Response:
    return httpx.Response(
        200, json={"result": {"page": page, "pages": pages, "total": total, "products": products}}
    )


def _make_products(start: int, count: int) -> list[dict]:
    return [
        {"productId": i, "sku": f"SKU-{i}", "name": f"Product {i}", "active": True, "price": 100 + i}
        for i in range(start, start + count)
    ]


def test_fetch_all_supplier_products_paginates_without_hardcoding():
    """3 pages / 5 products, mirroring the real sandbox shape — but the
    sync code itself never hard-codes either number, only this fixture
    does."""
    pages_data = {1: _make_products(1, 2), 2: _make_products(3, 2), 3: _make_products(5, 1)}

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        assert "X-Email" in request.headers
        assert "X-Api-Token" in request.headers
        return _fake_page_response(page, pages=3, total=5, products=pages_data[page])

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = AllianceTekClient(
        products_url="https://sandbox.example.invalid/products",
        email="test@example.com",
        api_token="test-token",
        http_client=http_client,
    )
    try:
        products, reported_total, pages_fetched = fetch_all_supplier_products(client)
    finally:
        client.close()

    assert pages_fetched == 3
    assert reported_total == 5
    assert len(products) == 5
    assert [p["productId"] for p in products] == [1, 2, 3, 4, 5]


def test_fetch_all_supplier_products_single_page():
    def handler(request: httpx.Request) -> httpx.Response:
        return _fake_page_response(1, pages=1, total=2, products=_make_products(1, 2))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = AllianceTekClient(
        products_url="https://sandbox.example.invalid/products",
        email="test@example.com",
        api_token="test-token",
        http_client=http_client,
    )
    try:
        products, reported_total, pages_fetched = fetch_all_supplier_products(client)
    finally:
        client.close()

    assert pages_fetched == 1
    assert reported_total == 2
    assert len(products) == 2


def test_client_requires_credentials():
    with pytest.raises(SupplierApiConfigError):
        AllianceTekClient(products_url="https://x.invalid", email="", api_token="")


def test_client_requires_products_url():
    # products_url is only validated lazily, on the call that actually
    # needs it — the client itself has no required URLs at construction
    # time, since different callers need different subsets of the five
    # endpoints (see worker/alliancetek/client.py).
    client = AllianceTekClient(products_url="", email="a@example.com", api_token="tok")
    with pytest.raises(SupplierApiConfigError):
        client.list_products(1)


def test_list_products_retries_then_raises_after_exhausting_attempts():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = AllianceTekClient(
        products_url="https://sandbox.example.invalid/products",
        email="test@example.com",
        api_token="test-token",
        max_retries=2,
        retry_backoff_seconds=0.0,
        http_client=http_client,
    )
    try:
        with pytest.raises(SupplierApiError):
            client.list_products(1)
    finally:
        client.close()

    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# DB upsert — runs against the real dev Postgres (docker-compose `db`).
# Uses clearly-fake, high-numbered supplier_product_id values and cleans
# up after itself so it never pollutes the dev database.
# ---------------------------------------------------------------------------

_TEST_SUPPLIER_PRODUCT_IDS = [900001, 900002]


@pytest.fixture
def db_engine():
    engine = create_engine(get_settings().database_url)
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM supplier_products WHERE supplier_product_id = ANY(:ids)"),
            {"ids": _TEST_SUPPLIER_PRODUCT_IDS},
        )
    engine.dispose()


def test_upsert_supplier_products_insert_then_update_preserves_first_seen_at(db_engine):
    row = {
        "supplier_product_id": _TEST_SUPPLIER_PRODUCT_IDS[0],
        "supplier_sku": "5AM1-50",
        "supplier_name": "BPC 157 Acetate 5mg Lyophilized",
        "supplier_active": True,
        "supplier_price_cents": 2200,
        "raw_payload": {"productId": _TEST_SUPPLIER_PRODUCT_IDS[0], "sku": "5AM1-50"},
    }

    t0 = datetime.now(timezone.utc)
    with db_engine.begin() as conn:
        upsert_supplier_products(conn, [row], now=t0)

    with db_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT supplier_sku, supplier_active, first_seen_at, last_seen_at, "
                "pg_typeof(supplier_sku)::text AS sku_type "
                "FROM supplier_products WHERE supplier_product_id = :id"
            ),
            {"id": _TEST_SUPPLIER_PRODUCT_IDS[0]},
        ).one()
        assert result.supplier_sku == "5AM1-50"
        assert result.sku_type == "text"
        assert result.supplier_active is True
        first_seen_at_1 = result.first_seen_at
        last_seen_at_1 = result.last_seen_at

    # Re-sync: same product, now inactive, later timestamp.
    t1 = t0 + timedelta(minutes=5)
    updated_row = {**row, "supplier_active": False}
    with db_engine.begin() as conn:
        upsert_supplier_products(conn, [updated_row], now=t1)

    with db_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT supplier_active, first_seen_at, last_seen_at "
                "FROM supplier_products WHERE supplier_product_id = :id"
            ),
            {"id": _TEST_SUPPLIER_PRODUCT_IDS[0]},
        ).one()
        assert result.supplier_active is False
        assert result.first_seen_at == first_seen_at_1  # unchanged across re-sync
        assert result.last_seen_at > last_seen_at_1


def test_upsert_supplier_products_classifies_insert_update_unchanged(db_engine):
    row = {
        "supplier_product_id": _TEST_SUPPLIER_PRODUCT_IDS[0],
        "supplier_sku": "5AM1-50",
        "supplier_name": "BPC 157 Acetate 5mg Lyophilized",
        "supplier_active": True,
        "supplier_price_cents": 2200,
        "raw_payload": {"productId": _TEST_SUPPLIER_PRODUCT_IDS[0], "sku": "5AM1-50"},
    }

    with db_engine.begin() as conn:
        result = upsert_supplier_products(conn, [row], now=datetime.now(timezone.utc))
    assert (result.inserted, result.updated, result.unchanged) == (1, 0, 0)

    # Re-syncing the identical payload should count as unchanged, not updated.
    with db_engine.begin() as conn:
        result = upsert_supplier_products(conn, [row], now=datetime.now(timezone.utc))
    assert (result.inserted, result.updated, result.unchanged) == (0, 0, 1)

    changed_row = {**row, "supplier_active": False}
    with db_engine.begin() as conn:
        result = upsert_supplier_products(conn, [changed_row], now=datetime.now(timezone.utc))
    assert (result.inserted, result.updated, result.unchanged) == (0, 1, 0)


def test_upsert_supplier_products_reports_changed_identity_ids_not_price_only(db_engine):
    row = {
        "supplier_product_id": _TEST_SUPPLIER_PRODUCT_IDS[0],
        "supplier_sku": "5AM1-50",
        "supplier_name": "BPC 157 Acetate 5mg Lyophilized",
        "supplier_active": True,
        "supplier_price_cents": 2200,
        "raw_payload": {"productId": _TEST_SUPPLIER_PRODUCT_IDS[0], "sku": "5AM1-50"},
    }
    with db_engine.begin() as conn:
        upsert_supplier_products(conn, [row], now=datetime.now(timezone.utc))

    # Price-only change: not an identity change.
    price_changed_row = {**row, "supplier_price_cents": 2500}
    with db_engine.begin() as conn:
        result = upsert_supplier_products(conn, [price_changed_row], now=datetime.now(timezone.utc))
    assert result.updated == 1
    assert result.changed_identity_ids == []

    # SKU change: an identity change.
    sku_changed_row = {**price_changed_row, "supplier_sku": "5AM1-50-RENAMED"}
    with db_engine.begin() as conn:
        result = upsert_supplier_products(conn, [sku_changed_row], now=datetime.now(timezone.utc))
    assert result.updated == 1
    assert result.changed_identity_ids == [_TEST_SUPPLIER_PRODUCT_IDS[0]]


def test_upsert_supplier_products_never_touches_storefront_tables(db_engine):
    """Regression guard: supplier sync must never *grant* sellability —
    it never creates a mapping and never sets is_sellable=True. It MAY
    revoke both (see reconcile_mapping_drift tests below), which is a
    restriction, not a grant, so this guard only checks that plain
    upserts with no drift leave row counts unchanged."""
    with db_engine.connect() as conn:
        variants_before = conn.execute(text("SELECT count(*) FROM product_variants")).scalar_one()
        mappings_before = conn.execute(text("SELECT count(*) FROM supplier_product_mappings")).scalar_one()

    rows = [
        {
            "supplier_product_id": pid,
            "supplier_sku": f"SKU-{pid}",
            "supplier_name": f"Product {pid}",
            "supplier_active": True,
            "supplier_price_cents": None,
            "raw_payload": {"productId": pid},
        }
        for pid in _TEST_SUPPLIER_PRODUCT_IDS
    ]

    with db_engine.begin() as conn:
        upsert_supplier_products(conn, rows, now=datetime.now(timezone.utc))

    with db_engine.connect() as conn:
        variants_after = conn.execute(text("SELECT count(*) FROM product_variants")).scalar_one()
        mappings_after = conn.execute(text("SELECT count(*) FROM supplier_product_mappings")).scalar_one()

    assert variants_after == variants_before
    assert mappings_after == mappings_before


# ---------------------------------------------------------------------------
# Validation failure path — should raise before ever touching the database.
# ---------------------------------------------------------------------------


def test_run_sync_raises_on_total_mismatch(monkeypatch):
    def fake_fetch_all_supplier_products(client):
        # Claims 5 total but only 1 was actually collected.
        return ([{"productId": 1, "sku": "X", "name": "Y", "active": True}], 5, 1)

    monkeypatch.setattr(sync_module, "fetch_all_supplier_products", fake_fetch_all_supplier_products)
    monkeypatch.setattr(
        sync_module,
        "AllianceTekClient",
        type(
            "FakeClient",
            (),
            {
                "close": lambda self: None,
                "from_settings": classmethod(lambda cls, *a, **k: cls()),
                "from_settings_for_supplier": classmethod(lambda cls, *a, **k: cls()),
            },
        ),
    )

    settings = worker_config.Settings(
        supplier_api_products_url="https://sandbox.example.invalid/products",
        supplier_api_email="a@example.com",
        supplier_api_token="tok",
        supplier_keys="umsrx",
    )
    monkeypatch.setattr(sync_module, "get_settings", lambda: settings)

    with pytest.raises(SupplierSyncValidationError):
        sync_module.run_sync()


def test_run_sync_reports_summary_and_skips_unmappable_rows(monkeypatch, db_engine):
    """One good record and one record missing a required field (no SKU
    under any known name) — the sync should still upsert the good row and
    report the bad one as an error, rather than aborting entirely.

    Padded with unchanged filler for every real currently-MAPPED supplier
    product so this stays under _MAX_DISAPPEARED_FRACTION — see
    _unchanged_fetch_rows_for_currently_mapped's docstring below."""
    valid = {
        "productId": _TEST_SUPPLIER_PRODUCT_IDS[0],
        "sku": "5AM1-50",
        "name": "BPC 157 5mg",
        "active": True,
        "price": 2200,
    }
    unmappable = {"productId": _TEST_SUPPLIER_PRODUCT_IDS[1], "name": "No SKU Field", "active": True}

    with db_engine.connect() as conn:
        filler = _unchanged_fetch_rows_for_currently_mapped(conn)
    fetch_payload = [valid, unmappable, *filler]

    def fake_fetch_all_supplier_products(client):
        return (fetch_payload, len(fetch_payload), 1)

    monkeypatch.setattr(sync_module, "fetch_all_supplier_products", fake_fetch_all_supplier_products)
    monkeypatch.setattr(
        sync_module,
        "AllianceTekClient",
        type(
            "FakeClient",
            (),
            {
                "close": lambda self: None,
                "from_settings": classmethod(lambda cls, *a, **k: cls()),
                "from_settings_for_supplier": classmethod(lambda cls, *a, **k: cls()),
            },
        ),
    )
    settings = worker_config.Settings(
        supplier_api_products_url="https://sandbox.example.invalid/products",
        supplier_api_email="a@example.com",
        supplier_api_token="tok",
        supplier_keys="umsrx",
    )
    monkeypatch.setattr(sync_module, "get_settings", lambda: settings)

    result = sync_module.run_sync(engine=db_engine)
    assert result.retrieved == len(fetch_payload)
    assert result.inserted == 1
    assert result.updated == 0
    assert result.unchanged == len(filler)
    assert result.errors == 1

    # Re-run with the identical payload: the mappable row is now unchanged,
    # and the same bad record still errors rather than crashing the sync.
    result2 = sync_module.run_sync(engine=db_engine)
    assert result2.retrieved == len(fetch_payload)
    assert result2.inserted == 0
    assert result2.updated == 0
    assert result2.unchanged == len(filler) + 1
    assert result2.errors == 1


# ---------------------------------------------------------------------------
# Reconciliation — supplier data changing/disappearing under an approved
# mapping must revoke it, never the other way around. Worker has no
# dependency on services/api's ORM, so fixtures seed products/
# product_variants/supplier_product_mappings with raw SQL, same as
# reconciliation.py itself only ever touches these tables via hand-mirrored
# Core Tables, never an ORM import.
# ---------------------------------------------------------------------------


def _seed_supplier_product(conn, *, supplier_product_id, sku, name, active=True):
    conn.execute(
        text(
            "INSERT INTO supplier_products "
            "(supplier_product_id, supplier_sku, supplier_name, supplier_active, raw_payload, "
            " first_seen_at, last_seen_at, created_at, updated_at) "
            "VALUES (:id, :sku, :name, :active, CAST(:payload AS jsonb), now(), now(), now(), now())"
        ),
        {
            "id": supplier_product_id,
            "sku": sku,
            "name": name,
            "active": active,
            "payload": json.dumps({"productId": supplier_product_id}),
        },
    )


def _seed_mapped_variant(conn, *, supplier_product_id, supplier_sku, supplier_name, slug_suffix, sellable):
    product_id = conn.execute(
        text("INSERT INTO products (slug, name, images, is_active) VALUES (:slug, 'Test Widget', '[]'::jsonb, false) RETURNING id"),
        {"slug": f"test-worker-reconcile-{slug_suffix}"},
    ).scalar_one()
    variant_id = conn.execute(
        text(
            "INSERT INTO product_variants (product_id, sku, name, retail_price_cents, is_sellable) "
            "VALUES (:product_id, :sku, 'Test Widget 10mg', 1000, :sellable) RETURNING id"
        ),
        {"product_id": product_id, "sku": f"TC-TEST-WORKER-RECONCILE-{slug_suffix.upper()}", "sellable": sellable},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO supplier_product_mappings "
            "(product_variant_id, supplier_product_id, supplier_sku, supplier_name, mapping_status) "
            "VALUES (:variant_id, :supplier_product_id, :sku, :name, 'MAPPED')"
        ),
        {
            "variant_id": variant_id,
            "supplier_product_id": supplier_product_id,
            "sku": supplier_sku,
            "name": supplier_name,
        },
    )
    return variant_id


def _mapping_status_and_sellable(conn, variant_id):
    row = conn.execute(
        text(
            "SELECT pv.is_sellable, spm.mapping_status FROM product_variants pv "
            "JOIN supplier_product_mappings spm ON spm.product_variant_id = pv.id "
            "WHERE pv.id = :variant_id"
        ),
        {"variant_id": variant_id},
    ).one()
    return row.is_sellable, row.mapping_status


@pytest.fixture
def reconcile_engine():
    engine = create_engine(get_settings().database_url)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM products WHERE slug LIKE 'test-worker-reconcile-%'"))
        conn.execute(
            text("DELETE FROM supplier_products WHERE supplier_product_id = ANY(:ids)"),
            {"ids": _TEST_SUPPLIER_PRODUCT_IDS},
        )
    engine.dispose()


def test_reconcile_mapping_drift_marks_changed_and_deactivates_variant(reconcile_engine):
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-A", name="Widget A")
        variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0],
            supplier_sku="SKU-A",
            supplier_name="Widget A",
            slug_suffix="changed",
            sellable=True,
        )

        result = reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            disappeared_supplier_product_ids=[],
            supplier_key="umsrx",
        )
        assert result.mappings_marked_changed == 1
        assert result.mappings_marked_missing == 0
        assert result.variants_deactivated == 1

        is_sellable, mapping_status = _mapping_status_and_sellable(conn, variant_id)
        assert is_sellable is False
        assert mapping_status == "CHANGED"


def test_reconcile_mapping_drift_marks_missing_and_deactivates_variant(reconcile_engine):
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-B", name="Widget B")
        variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0],
            supplier_sku="SKU-B",
            supplier_name="Widget B",
            slug_suffix="missing",
            sellable=True,
        )

        result = reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[],
            disappeared_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            supplier_key="umsrx",
        )
        assert result.mappings_marked_missing == 1
        assert result.variants_deactivated == 1

        is_sellable, mapping_status = _mapping_status_and_sellable(conn, variant_id)
        assert is_sellable is False
        assert mapping_status == "MISSING"


def test_reconcile_mapping_drift_is_idempotent_for_already_downgraded_mapping(reconcile_engine):
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-C", name="Widget C")
        variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0],
            supplier_sku="SKU-C",
            supplier_name="Widget C",
            slug_suffix="idempotent",
            sellable=True,
        )

        first = reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            disappeared_supplier_product_ids=[],
            supplier_key="umsrx",
        )
        assert first.mappings_marked_changed == 1

        # Running again against the same (already-CHANGED) mapping must
        # not double-count it or touch it further — WHERE mapping_status
        # = 'MAPPED' guards this.
        second = reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            disappeared_supplier_product_ids=[],
            supplier_key="umsrx",
        )
        assert second.mappings_marked_changed == 0
        assert second.variants_deactivated == 0

        is_sellable, mapping_status = _mapping_status_and_sellable(conn, variant_id)
        assert is_sellable is False
        assert mapping_status == "CHANGED"


def test_reconcile_mapping_drift_leaves_unrelated_variant_untouched(reconcile_engine):
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-D", name="Widget D")
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[1], sku="SKU-E", name="Widget E")
        changed_variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0],
            supplier_sku="SKU-D",
            supplier_name="Widget D",
            slug_suffix="unrelated-changed",
            sellable=True,
        )
        untouched_variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[1],
            supplier_sku="SKU-E",
            supplier_name="Widget E",
            slug_suffix="unrelated-untouched",
            sellable=True,
        )

        reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            disappeared_supplier_product_ids=[],
            supplier_key="umsrx",
        )

        changed_sellable, changed_status = _mapping_status_and_sellable(conn, changed_variant_id)
        assert (changed_sellable, changed_status) == (False, "CHANGED")

        untouched_sellable, untouched_status = _mapping_status_and_sellable(conn, untouched_variant_id)
        assert (untouched_sellable, untouched_status) == (True, "MAPPED")


def test_get_mapped_supplier_product_ids_only_returns_mapped_status(reconcile_engine):
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0], sku="SKU-F", name="Widget F")
        _seed_mapped_variant(
            conn,
            supplier_product_id=_TEST_SUPPLIER_PRODUCT_IDS[0],
            supplier_sku="SKU-F",
            supplier_name="Widget F",
            slug_suffix="ids-mapped",
            sellable=False,
        )
        reconcile_mapping_drift(
            conn,
            changed_supplier_product_ids=[_TEST_SUPPLIER_PRODUCT_IDS[0]],
            disappeared_supplier_product_ids=[],
            supplier_key="umsrx",
        )
        # Now CHANGED, not MAPPED — must not appear in the result.
        assert _TEST_SUPPLIER_PRODUCT_IDS[0] not in get_mapped_supplier_product_ids(conn, "umsrx")


def _unchanged_fetch_rows_for_currently_mapped(conn, *, omit: set[int] = frozenset()) -> list[dict]:
    """Builds AllianceTek-shaped rows that echo back every currently-
    MAPPED supplier product completely unchanged, except ids in `omit`.

    A real sync always fetches the *whole* catalog, so a test proving
    run_sync's reactive wiring must do the same — a tiny 1-item fake
    fetch against the shared dev DB makes every other currently-mapped
    supplier product look "disappeared" (nothing in the fetch mentions
    it), which is exactly the bug that motivated
    `_MAX_DISAPPEARED_FRACTION` in sync.py. Padding the fetch with
    unchanged rows for everything real keeps these tests honest without
    touching real data (they're unchanged, so the upsert is a no-op) and
    without depending on real data being absent.
    """
    rows = conn.execute(
        text(
            "SELECT DISTINCT sp.supplier_product_id, sp.supplier_sku, sp.supplier_name, sp.supplier_active "
            "FROM supplier_product_mappings spm "
            "JOIN supplier_products sp ON sp.supplier_product_id = spm.supplier_product_id "
            "WHERE spm.mapping_status = 'MAPPED'"
        )
    ).all()
    return [
        {"productId": row.supplier_product_id, "sku": row.supplier_sku, "name": row.supplier_name, "active": row.supplier_active}
        for row in rows
        if row.supplier_product_id not in omit
    ]


def test_run_sync_deactivates_variant_when_supplier_sku_changes_end_to_end(monkeypatch, reconcile_engine):
    """Proves the reactive path is actually wired into run_sync, not just
    unit-tested in isolation: a real sync run, whose fetched payload
    renames a mapped supplier product's SKU, must downgrade the mapping
    and deactivate the variant in the same transaction as the upsert."""
    supplier_product_id = _TEST_SUPPLIER_PRODUCT_IDS[0]
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=supplier_product_id, sku="SKU-G", name="Widget G")
        variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=supplier_product_id,
            supplier_sku="SKU-G",
            supplier_name="Widget G",
            slug_suffix="e2e-changed",
            sellable=True,
        )
        filler = _unchanged_fetch_rows_for_currently_mapped(conn, omit={supplier_product_id})

    renamed = {"productId": supplier_product_id, "sku": "SKU-G-RENAMED", "name": "Widget G", "active": True}
    fetch_payload = [renamed, *filler]

    def fake_fetch_all_supplier_products(client):
        return (fetch_payload, len(fetch_payload), 1)

    monkeypatch.setattr(sync_module, "fetch_all_supplier_products", fake_fetch_all_supplier_products)
    monkeypatch.setattr(
        sync_module,
        "AllianceTekClient",
        type(
            "FakeClient",
            (),
            {
                "close": lambda self: None,
                "from_settings": classmethod(lambda cls, *a, **k: cls()),
                "from_settings_for_supplier": classmethod(lambda cls, *a, **k: cls()),
            },
        ),
    )
    settings = worker_config.Settings(
        supplier_api_products_url="https://sandbox.example.invalid/products",
        supplier_api_email="a@example.com",
        supplier_api_token="tok",
        supplier_keys="umsrx",
    )
    monkeypatch.setattr(sync_module, "get_settings", lambda: settings)

    result = sync_module.run_sync(engine=reconcile_engine)
    assert result.mappings_changed == 1
    assert result.variants_deactivated == 1

    with reconcile_engine.connect() as conn:
        is_sellable, mapping_status = _mapping_status_and_sellable(conn, variant_id)
    assert is_sellable is False
    assert mapping_status == "CHANGED"


def test_run_sync_deactivates_variant_when_supplier_product_disappears_end_to_end(monkeypatch, reconcile_engine):
    """Same proof as above, for the disappeared path: a real sync run
    whose fetch simply omits a currently-MAPPED supplier product (while
    still fetching everything else — a complete, validated catalog) must
    mark that mapping MISSING and deactivate its variant."""
    supplier_product_id = _TEST_SUPPLIER_PRODUCT_IDS[0]
    with reconcile_engine.begin() as conn:
        _seed_supplier_product(conn, supplier_product_id=supplier_product_id, sku="SKU-H", name="Widget H")
        variant_id = _seed_mapped_variant(
            conn,
            supplier_product_id=supplier_product_id,
            supplier_sku="SKU-H",
            supplier_name="Widget H",
            slug_suffix="e2e-missing",
            sellable=True,
        )
        # Omit our target id entirely — everything else currently mapped
        # is still fetched, so this is a complete catalog minus one
        # genuinely-discontinued product, not a truncated/broken fetch.
        fetch_payload = _unchanged_fetch_rows_for_currently_mapped(conn, omit={supplier_product_id})

    def fake_fetch_all_supplier_products(client):
        return (fetch_payload, len(fetch_payload), 1)

    monkeypatch.setattr(sync_module, "fetch_all_supplier_products", fake_fetch_all_supplier_products)
    monkeypatch.setattr(
        sync_module,
        "AllianceTekClient",
        type(
            "FakeClient",
            (),
            {
                "close": lambda self: None,
                "from_settings": classmethod(lambda cls, *a, **k: cls()),
                "from_settings_for_supplier": classmethod(lambda cls, *a, **k: cls()),
            },
        ),
    )
    settings = worker_config.Settings(
        supplier_api_products_url="https://sandbox.example.invalid/products",
        supplier_api_email="a@example.com",
        supplier_api_token="tok",
        supplier_keys="umsrx",
    )
    monkeypatch.setattr(sync_module, "get_settings", lambda: settings)

    result = sync_module.run_sync(engine=reconcile_engine)
    assert result.mappings_missing == 1
    assert result.variants_deactivated == 1

    with reconcile_engine.connect() as conn:
        is_sellable, mapping_status = _mapping_status_and_sellable(conn, variant_id)
    assert is_sellable is False
    assert mapping_status == "MISSING"


def test_run_sync_aborts_without_writing_if_most_of_the_catalog_disappears(monkeypatch, reconcile_engine):
    """Regression guard for the exact bug this file's own tests hit
    during development: a small/truncated-looking fetch must never be
    allowed to mass-mark the real mapped catalog as disappeared. Fetches
    only a couple of unrelated fake products (not the real mapped ones,
    and not padded with filler) — run_sync must raise before writing
    anything, and the real mapping_status values must be provably
    untouched afterward."""
    with reconcile_engine.connect() as conn:
        mapped_before = dict(
            conn.execute(
                text("SELECT supplier_product_id, mapping_status FROM supplier_product_mappings WHERE mapping_status = 'MAPPED'")
            ).all()
        )
    assert mapped_before, "expected at least one real MAPPED row for this guard to be meaningful"

    unrelated_products = [
        {"productId": 700001, "sku": "UNRELATED-1", "name": "Unrelated 1", "active": True},
        {"productId": 700002, "sku": "UNRELATED-2", "name": "Unrelated 2", "active": True},
    ]

    def fake_fetch_all_supplier_products(client):
        return (unrelated_products, len(unrelated_products), 1)

    monkeypatch.setattr(sync_module, "fetch_all_supplier_products", fake_fetch_all_supplier_products)
    monkeypatch.setattr(
        sync_module,
        "AllianceTekClient",
        type(
            "FakeClient",
            (),
            {
                "close": lambda self: None,
                "from_settings": classmethod(lambda cls, *a, **k: cls()),
                "from_settings_for_supplier": classmethod(lambda cls, *a, **k: cls()),
            },
        ),
    )
    settings = worker_config.Settings(
        supplier_api_products_url="https://sandbox.example.invalid/products",
        supplier_api_email="a@example.com",
        supplier_api_token="tok",
        supplier_keys="umsrx",
    )
    monkeypatch.setattr(sync_module, "get_settings", lambda: settings)

    try:
        with pytest.raises(SupplierSyncValidationError, match="Aborting without changing any mapping"):
            sync_module.run_sync(engine=reconcile_engine)

        with reconcile_engine.connect() as conn:
            mapped_after = dict(
                conn.execute(
                    text("SELECT supplier_product_id, mapping_status FROM supplier_product_mappings WHERE supplier_product_id = ANY(:ids)"),
                    {"ids": list(mapped_before)},
                ).all()
            )
        assert mapped_after == mapped_before
    finally:
        # Belt and suspenders beyond the transactional rollback: the
        # unrelated fake supplier_products rows (if the upsert somehow
        # did commit) must never linger.
        with reconcile_engine.begin() as conn:
            conn.execute(text("DELETE FROM supplier_products WHERE supplier_product_id IN (700001, 700002)"))
