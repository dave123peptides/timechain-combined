from __future__ import annotations

from worker.supplier_sync.production_report import CatalogEntry, compare_catalogs


def _entry(product_id: int, sku: str, name: str) -> CatalogEntry:
    return CatalogEntry(supplier_product_id=product_id, supplier_sku=sku, supplier_name=name)


def test_identical_entries_are_same():
    baseline = [_entry(111, "SKU-1", "5 Amino 1MQ 10mg")]
    production = [_entry(111, "SKU-1", "5 Amino 1MQ 10mg")]

    report = compare_catalogs(baseline, production)

    assert [e.supplier_sku for e in report.same] == ["SKU-1"]
    assert report.changed == []
    assert report.missing == []
    assert report.new == []


def test_different_product_id_on_matching_sku_is_changed_not_same():
    """The core scenario this tool exists for: Sandbox and Production
    never share productId numbering, so a productId mismatch on a
    matched SKU must never be silently treated as "same"."""
    baseline = [_entry(111, "SKU-1", "5 Amino 1MQ 10mg")]
    production = [_entry(999, "SKU-1", "5 Amino 1MQ 10mg")]

    report = compare_catalogs(baseline, production)

    assert report.same == []
    assert len(report.changed) == 1
    changed = report.changed[0]
    assert changed.supplier_sku == "SKU-1"
    assert changed.differences == ("productId",)
    assert changed.baseline.supplier_product_id == 111
    assert changed.production.supplier_product_id == 999


def test_name_change_on_matching_sku_is_changed():
    baseline = [_entry(111, "SKU-1", "5 Amino 1MQ 10mg (Vial)")]
    production = [_entry(111, "SKU-1", "5-Amino-1MQ 10mg Vial")]

    report = compare_catalogs(baseline, production)

    assert len(report.changed) == 1
    assert report.changed[0].differences == ("name",)


def test_both_product_id_and_name_differ_reports_both():
    baseline = [_entry(111, "SKU-1", "Old Name")]
    production = [_entry(999, "SKU-1", "New Name")]

    report = compare_catalogs(baseline, production)

    assert report.changed[0].differences == ("productId", "name")


def test_sku_only_in_baseline_is_missing():
    baseline = [_entry(111, "SKU-1", "Discontinued Product")]
    production: list[CatalogEntry] = []

    report = compare_catalogs(baseline, production)

    assert report.same == []
    assert report.changed == []
    assert [e.supplier_sku for e in report.missing] == ["SKU-1"]
    assert report.new == []


def test_sku_only_in_production_is_new():
    baseline: list[CatalogEntry] = []
    production = [_entry(222, "SKU-2", "Newly Listed Product")]

    report = compare_catalogs(baseline, production)

    assert report.same == []
    assert report.changed == []
    assert report.missing == []
    assert [e.supplier_sku for e in report.new] == ["SKU-2"]


def test_mixed_catalog_categorizes_every_entry_correctly():
    baseline = [
        _entry(1, "SAME", "Same Product"),
        _entry(2, "CHANGED", "Old Name"),
        _entry(3, "GONE", "No Longer In Production"),
    ]
    production = [
        _entry(1, "SAME", "Same Product"),
        _entry(999, "CHANGED", "Old Name"),  # productId drifted
        _entry(4, "FRESH", "Brand New Product"),
    ]

    report = compare_catalogs(baseline, production)

    assert {e.supplier_sku for e in report.same} == {"SAME"}
    assert {e.supplier_sku for e in report.changed} == {"CHANGED"}
    assert {e.supplier_sku for e in report.missing} == {"GONE"}
    assert {e.supplier_sku for e in report.new} == {"FRESH"}


def test_compare_catalogs_never_mutates_inputs():
    baseline = [_entry(1, "SKU-1", "Name")]
    production = [_entry(2, "SKU-1", "Name")]
    baseline_copy = list(baseline)
    production_copy = list(production)

    compare_catalogs(baseline, production)

    assert baseline == baseline_copy
    assert production == production_copy
