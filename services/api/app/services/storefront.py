from __future__ import annotations

import logging
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductCoa, ProductVariant
from app.models.events import ConsentRecord
from app.models.orders import Order, OrderEvent, OrderItem
from app.models.payments import Payment
from app.models.settings import SystemSetting
from app.constants.bulk_discounts import discounted_unit_price_cents
from app.constants.forms import FORM_LABEL as _FORM_LABEL
from app.services.mapping_status import get_active_mapping, get_mapping_status

logger = logging.getLogger(__name__)

# Bump these whenever the corresponding page's text actually changes —
# stamped onto every ConsentRecord so historical orders show exactly
# what the customer agreed to, regardless of later edits.
RUO_TERMS_VERSION = "2026-08-13"
TERMS_VERSION = "2026-08-13"
PRIVACY_VERSION = "2026-08-13"

_SHIPPING_RATE_SETTING_KEY = "shipping.us_flat_rate_cents"


class StorefrontError(RuntimeError):
    """Raised when an order can't be created as submitted — e.g. a cart
    line item is no longer sellable, or has an invalid quantity. The
    route layer maps this to an HTTP 400 shown to the customer. Nothing
    is written to the database when this is raised."""


@dataclass(frozen=True)
class StorefrontVariant:
    """Customer-safe variant fields only — no sku exposed (that's an
    internal identifier), no supplier data of any kind."""

    id: uuid.UUID
    name: str
    format: str
    # Raw ProductVariant.form (e.g. "lyophilized"/"preconstituted"), for
    # the frontend to key format-specific content (reconstitution
    # instructions vs. ready-to-use copy) off of — `format` above is the
    # display label, not reliably parseable back into the raw value.
    form: Optional[str]
    strength: Optional[str]
    price_cents: int


@dataclass(frozen=True)
class StorefrontCoa:
    """One published Certificate of Analysis — customer-safe fields only.
    `client` (who the lab issued it to) and `source_file` stay internal:
    the customer verifies the certificate with the lab, not with us."""

    verify_code: str
    # ProductVariant.size_key shape ("10", "10/10/50", "10mL") so the
    # frontend groups these against the strength picker. See ProductCoa.
    strength: Optional[str]
    lot: str
    issued_on: date
    lab: str
    tests: list[str]
    pdf_url: str
    verify_url: Optional[str]


@dataclass(frozen=True)
class StorefrontProductSummary:
    slug: str
    name: str
    description: Optional[str]
    category: Optional[str]
    images: list[str]
    starting_price_cents: int
    # Full sellable variant list, not just the cheapest — the cart page
    # cross-references a variant_id from localStorage against this same
    # endpoint's response rather than needing a separate lookup call.
    variants: list[StorefrontVariant]
    # Certificate rollup, deliberately on the SUMMARY as well as the
    # detail (unlike `content`): ProductCard's COA badge and the /coa
    # index need it per product without a detail fetch each. A count and
    # a date per row is nothing like shipping the certificates themselves
    # to every card in a grid — those are on the detail only.
    coa_count: int = 0
    coa_latest_issued_on: Optional[date] = None
    # Safety Data Sheet; null renders as an honest "on request".
    sds_url: Optional[str] = None


@dataclass(frozen=True)
class StorefrontProductDetail:
    slug: str
    name: str
    description: Optional[str]
    category: Optional[str]
    images: list[str]
    variants: list[StorefrontVariant]
    # Structured PDP copy (overview/key_points/research_areas/pairs_with/
    # faq) — see Product.content's docstring. Never on the list summary,
    # only the detail — no reason to ship this much text to every card in
    # a grid.
    content: dict
    # Every published certificate for this product, ordered by strength
    # (ascending, numerically) then newest first — the order the Lab
    # report tab renders them in. Empty list is the honest "none held"
    # state, which the frontend renders as "available on request".
    coas: list[StorefrontCoa] = field(default_factory=list)
    # See StorefrontProductSummary.
    sds_url: Optional[str] = None


@dataclass(frozen=True)
class StorefrontCoaIndexEntry:
    """/coa's unit: one sellable product and all of its published
    certificates. Products with none are absent — the index page merges
    this with the product list to show those as "on request"."""

    slug: str
    name: str
    coas: list[StorefrontCoa]


@dataclass(frozen=True)
class OrderItemRequest:
    variant_id: uuid.UUID
    quantity: int


@dataclass(frozen=True)
class ConsentInput:
    """All three are required to place an order — see create_order.
    Deliberately booleans only, not versions: the client says *whether*
    it agreed, the backend says *to what* (see the module-level
    *_VERSION constants), for the same reason the client doesn't get to
    say the price."""

    age_confirmed: bool
    ruo_acknowledged: bool
    terms_accepted: bool


@dataclass(frozen=True)
class ShippingQuote:
    country: str
    amount_cents: int


@dataclass(frozen=True)
class QuoteLine:
    variant_id: uuid.UUID
    # None of the fields below sku are customer-facing (see
    # StorefrontVariant, which deliberately omits them) — kept here only
    # so create_order can snapshot them onto OrderItem without a second
    # DB round-trip. The API response model for /checkout/quote simply
    # doesn't declare these fields, so they never serialize out.
    sku: str
    name: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int
    wholesale_cost_cents: Optional[int]
    supplier_product_id: int
    supplier_sku: str
    supplier_name: str


@dataclass(frozen=True)
class Quote:
    items: list[QuoteLine]
    subtotal_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int


def _format_label(form: Optional[str]) -> str:
    return _FORM_LABEL.get(form or "", form or "—")


def calculate_tax_cents(session: Session, *, subtotal_cents: int, shipping_address: dict) -> int:
    """Real computed step, not a constant inlined at call sites — a
    future real tax engine only needs to change this function's body.
    Temporary implementation: always 0. Callers must not assume this
    stays 0 — always read the return value, never inline a 0 of your
    own (same discipline as shipping: see get_shipping_quote)."""
    return 0


_ORDER_NUMBER_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L — avoids visual ambiguity


def _generate_public_order_number() -> str:
    suffix = "".join(secrets.choice(_ORDER_NUMBER_ALPHABET) for _ in range(6))
    # "PEN-" (not the vial site's "TCP-"): both storefronts append to the
    # same Google Sheet tab, and this prefix is how their rows are told apart.
    return f"PEN-{suffix}"


def _resolve_and_price_items(session: Session, items: list[OrderItemRequest]) -> tuple[list[QuoteLine], int]:
    """Steps shared by both /checkout/quote and /checkout/create: load
    each variant, verify is_sellable, verify its supplier mapping is
    actually MAPPED (not just is_sellable — see create_order's original
    docstring note on why that's checked explicitly), and price from the
    database. Raises StorefrontError (nothing written) on the first
    problem found. Never reads a price, name, or sku from `items` —
    OrderItemRequest structurally has no such fields."""
    if not items:
        raise StorefrontError("Cannot proceed with an empty cart.")

    lines: list[QuoteLine] = []
    subtotal_cents = 0
    for item in items:
        if item.quantity <= 0:
            raise StorefrontError(f"Invalid quantity for item {item.variant_id}.")

        variant = session.get(ProductVariant, item.variant_id)
        if variant is None or not variant.is_sellable:
            label = variant.name if variant is not None else str(item.variant_id)
            raise StorefrontError(f"'{label}' is no longer available and was not added to your order.")

        if get_mapping_status(session, variant.id) != "MAPPED":
            raise StorefrontError(f"'{variant.name}' is no longer available and was not added to your order.")

        # get_mapping_status only confirms MAPPED exists; fetch the row
        # itself here to snapshot the supplier identity backing it. Same
        # "MAPPED and active" row by construction — mapping_status.py's
        # own docstring guarantees these two calls agree.
        mapping = get_active_mapping(session, variant.id)
        if mapping is None:
            raise StorefrontError(f"'{variant.name}' is no longer available and was not added to your order.")

        # Bulk quantity discount is per line — buying 5 of this exact
        # variant qualifies, buying 5 total across different variants
        # doesn't. See app.constants.bulk_discounts for the tier table.
        unit_price_cents = discounted_unit_price_cents(variant.retail_price_cents, item.quantity)
        total_price_cents = unit_price_cents * item.quantity
        subtotal_cents += total_price_cents
        lines.append(
            QuoteLine(
                variant_id=variant.id,
                sku=variant.sku,
                name=variant.name,
                quantity=item.quantity,
                unit_price_cents=unit_price_cents,
                total_price_cents=total_price_cents,
                wholesale_cost_cents=variant.wholesale_cost_cents,
                supplier_product_id=mapping.supplier_product_id,
                supplier_sku=mapping.supplier_sku,
                supplier_name=mapping.supplier_name,
            )
        )
    return lines, subtotal_cents


def build_quote(session: Session, *, items: list[OrderItemRequest], country: str = "US") -> Quote:
    """POST /api/v1/checkout/quote's implementation. Read-only — writes
    nothing — a pure preview of what create_order would charge. Shares
    its validation/pricing/shipping/tax logic with create_order exactly
    (via _resolve_and_price_items / get_shipping_quote /
    calculate_tax_cents) so the two can never quietly disagree."""
    lines, subtotal_cents = _resolve_and_price_items(session, items)
    shipping_quote = get_shipping_quote(session, country=country)
    tax_cents = calculate_tax_cents(
        session, subtotal_cents=subtotal_cents, shipping_address={"country": country}
    )
    return Quote(
        items=lines,
        subtotal_cents=subtotal_cents,
        shipping_cents=shipping_quote.amount_cents,
        tax_cents=tax_cents,
        total_cents=subtotal_cents + shipping_quote.amount_cents + tax_cents,
    )


def get_shipping_quote(session: Session, *, country: str = "US") -> ShippingQuote:
    """US-only at launch. Reads the flat rate from system_settings —
    raises rather than silently defaulting to free shipping if the
    setting is somehow missing, same "fail loudly" stance as everywhere
    else money is computed in this codebase."""
    if country != "US":
        raise StorefrontError("We currently ship within the United States only.")

    setting = session.execute(
        select(SystemSetting).where(SystemSetting.key == _SHIPPING_RATE_SETTING_KEY)
    ).scalar_one_or_none()
    if setting is None:
        raise StorefrontError("Shipping is not currently configured. Please try again shortly.")

    amount_cents = setting.value.get("amount_cents")
    if not isinstance(amount_cents, int):
        raise StorefrontError("Shipping is not currently configured correctly. Please try again shortly.")

    return ShippingQuote(country=country, amount_cents=amount_cents)


# Sort keys accepted by list_sellable_products / GET /shop/products.
# Sorting stays in Python rather than SQL on purpose: starting_price_cents
# is min() over each product's variants, computed AFTER the flat
# variant+product rows are grouped into a dict below. Ordering by it in
# SQL would need a GROUP BY or window subquery restructuring of the whole
# query — real complexity for 32 products with no pagination. Revisit if
# the catalog ever grows enough to need LIMIT/OFFSET.
_PRODUCT_SORTERS = {
    "name": lambda summary: (summary.name.lower(),),
    "price_asc": lambda summary: (summary.starting_price_cents, summary.name.lower()),
    "price_desc": lambda summary: (-summary.starting_price_cents, summary.name.lower()),
}


def _escape_like(term: str) -> str:
    """Escape LIKE/ILIKE metacharacters in user input.

    Without this a search for "%" matches the entire catalog and "_"
    matches any single character — a search box that silently ignores its
    own query. Backslash first, or it would double-escape the escapes
    added after it.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _coa_sort_key(coa: ProductCoa) -> tuple[float, str, float, str]:
    """Strength ascending by its leading number ("10" < "20" < "100";
    "10mL" sorts by 10; a blend key like "10/10/50" by its first
    component), then newest certificate first, then verify_code so the
    order is total. String sort alone would put "100" before "20"."""
    strength = coa.strength or ""
    match = re.match(r"\d+(?:\.\d+)?", strength)
    leading = float(match.group(0)) if match else float("inf")
    return (leading, strength, -coa.issued_on.toordinal(), coa.verify_code)


def _to_storefront_coa(coa: ProductCoa) -> StorefrontCoa:
    return StorefrontCoa(
        verify_code=coa.verify_code,
        strength=coa.strength,
        lot=coa.lot,
        issued_on=coa.issued_on,
        lab=coa.lab,
        tests=list(coa.tests or []),
        pdf_url=coa.pdf_url,
        verify_url=coa.verify_url,
    )


def _published_coas_by_product(session: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[StorefrontCoa]]:
    """Published certificates for the given products, each list already
    in display order. Only ever reads is_published rows — an unpublished
    certificate must not leak through any storefront path."""
    if not product_ids:
        return {}
    rows = session.execute(
        select(ProductCoa).where(ProductCoa.product_id.in_(product_ids), ProductCoa.is_published.is_(True))
    ).scalars()
    grouped: dict[uuid.UUID, list[ProductCoa]] = {}
    for coa in rows:
        grouped.setdefault(coa.product_id, []).append(coa)
    return {
        product_id: [_to_storefront_coa(coa) for coa in sorted(coas, key=_coa_sort_key)]
        for product_id, coas in grouped.items()
    }


def _coa_rollup_by_product(session: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, date]]:
    """(count, latest issued_on) per product for the list summary — one
    GROUP BY, not a certificates fetch per card."""
    if not product_ids:
        return {}
    rows = session.execute(
        select(ProductCoa.product_id, func.count(ProductCoa.id), func.max(ProductCoa.issued_on))
        .where(ProductCoa.product_id.in_(product_ids), ProductCoa.is_published.is_(True))
        .group_by(ProductCoa.product_id)
    ).all()
    return {product_id: (count, latest) for product_id, count, latest in rows}


def list_sellable_products(
    session: Session,
    *,
    category: Optional[str] = None,
    form: Optional[str] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,
) -> list[StorefrontProductSummary]:
    """Every Product with at least one is_sellable=True variant. Queries
    only products/product_variants — never joins supplier_products or
    supplier_product_mappings, so there's nothing supplier-shaped to
    accidentally leak even before the response model strips fields.

    `category`/`form` are optional exact-match filters (see
    GET /shop/products in api/shop.py) — applied at the SQL level so
    filtering never touches products/variants that aren't sellable in
    the first place.

    `q` is a case-insensitive substring search over name/slug/description,
    also at the SQL level, ANDed with the other filters. Blank or
    whitespace-only input is treated as no filter rather than as a search
    for the empty string (which would match everything). Note the
    description clause contributes nothing until
    app.scripts.seed_pen_catalog has run — the column is NULL for
    every product before that, and NULL ILIKE ... yields NULL, which or_()
    correctly treats as not-true rather than as a match.

    `sort` is one of _PRODUCT_SORTERS; anything unrecognized falls back to
    name order rather than raising, so a hand-edited or stale URL can
    never error a public catalog page.
    """
    query = (
        select(ProductVariant, Product)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductVariant.is_sellable.is_(True))
        .order_by(Product.name, ProductVariant.retail_price_cents)
    )
    if category is not None:
        query = query.where(Product.category == category)
    if form is not None:
        query = query.where(ProductVariant.form == form)
    if q is not None and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        query = query.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.slug.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
            )
        )
    rows = session.execute(query).all()

    by_product: dict[uuid.UUID, tuple[Product, list[ProductVariant]]] = {}
    for variant, product in rows:
        by_product.setdefault(product.id, (product, []))[1].append(variant)

    coa_rollup = _coa_rollup_by_product(session, list(by_product))

    summaries = [
        StorefrontProductSummary(
            slug=product.slug,
            name=product.name,
            description=product.description,
            category=product.category,
            images=list(product.images or []),
            coa_count=coa_rollup.get(product.id, (0, None))[0],
            coa_latest_issued_on=coa_rollup.get(product.id, (0, None))[1],
            sds_url=product.sds_url,
            starting_price_cents=min(v.retail_price_cents for v in variants),
            variants=[
                StorefrontVariant(
                    id=variant.id,
                    name=variant.name,
                    format=_format_label(variant.form),
                    form=variant.form,
                    strength=variant.size_key,
                    price_cents=variant.retail_price_cents,
                )
                for variant in variants
            ],
        )
        for product, variants in by_product.values()
    ]
    summaries.sort(key=_PRODUCT_SORTERS.get(sort or "name", _PRODUCT_SORTERS["name"]))
    return summaries


def list_sellable_filter_options(session: Session) -> tuple[list[str], list[str]]:
    """Distinct (category, form) values actually present across sellable
    variants right now — drives the shop page's filter UI. Deliberately
    not app.constants.categories.CATEGORIES (that list is just an admin
    curation aid, unrelated to what's actually live), so this always
    matches the real catalog regardless of what categories/forms it ends
    up using. A category whose products all stop being sellable therefore
    disappears from the nav on its own — there is no empty-category state
    to guard against downstream.

    Categories come back alphabetically, which for the launch taxonomy
    happens to also be the intended merchandising order (GLP-1 & Metabolic
    ... Supplies last). That is a coincidence, not a design: if a future
    category sorts somewhere it shouldn't read, give the nav an explicit
    order rather than re-sorting this result.
    """
    rows = session.execute(
        select(Product.category, ProductVariant.form)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductVariant.is_sellable.is_(True))
        .distinct()
    ).all()
    categories = sorted({category for category, _ in rows if category})
    forms = sorted({form for _, form in rows if form})
    return categories, forms


def get_sellable_product_by_slug(session: Session, slug: str) -> Optional[StorefrontProductDetail]:
    """None if the product doesn't exist OR exists but has no sellable
    variants right now — both cases are "not available", indistinguishable
    to a customer and the route returns 404 for either."""
    product = session.execute(select(Product).where(Product.slug == slug)).scalar_one_or_none()
    if product is None:
        return None

    variants = list(
        session.execute(
            select(ProductVariant)
            .where(ProductVariant.product_id == product.id, ProductVariant.is_sellable.is_(True))
            .order_by(ProductVariant.retail_price_cents)
        ).scalars()
    )
    if not variants:
        return None

    return StorefrontProductDetail(
        slug=product.slug,
        name=product.name,
        description=product.description,
        category=product.category,
        images=list(product.images or []),
        coas=_published_coas_by_product(session, [product.id]).get(product.id, []),
        sds_url=product.sds_url,
        content=dict(product.content or {}),
        variants=[
            StorefrontVariant(
                id=variant.id,
                name=variant.name,
                format=_format_label(variant.form),
                form=variant.form,
                strength=variant.size_key,
                price_cents=variant.retail_price_cents,
            )
            for variant in variants
        ],
    )


def list_published_coas(session: Session) -> list[StorefrontCoaIndexEntry]:
    """Every published certificate, grouped by product, for /coa. Only
    products with at least one sellable variant — same visibility rule as
    the catalog, so a delisted product's paperwork disappears with it.
    Sorted by product name; each product's certificates are in Lab
    report order (see _coa_sort_key)."""
    sellable_ids = select(ProductVariant.product_id).where(ProductVariant.is_sellable.is_(True))
    products = list(
        session.execute(select(Product).where(Product.id.in_(sellable_ids)).order_by(Product.name)).scalars()
    )
    coas_by_product = _published_coas_by_product(session, [p.id for p in products])
    return [
        StorefrontCoaIndexEntry(slug=product.slug, name=product.name, coas=coas_by_product[product.id])
        for product in products
        if product.id in coas_by_product
    ]


def create_order(
    session: Session,
    *,
    email: str,
    shipping_address: dict,
    items: list[OrderItemRequest],
    consent: ConsentInput,
    payment_method: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
) -> Order:
    """POST /api/v1/checkout/create's implementation. Steps:

    1-3. validate cart / verify products+sellability / verify supplier
         mappings — _resolve_and_price_items.
    4.   calculate totals server-side — subtotal from
         _resolve_and_price_items, shipping from get_shipping_quote, tax
         from calculate_tax_cents. A client-submitted price, a variant
         disabled since it was cached client-side, or a mapping that's
         drifted can never reach an Order.
    5.   validate shipping — get_shipping_quote rejects non-US.
    6.   record consents — all three required, or nothing is written.
    7.   create internal order (public_order_number + access_token, both
         backend-generated — never a sequential/exposed database id).
    8.   create immutable OrderItem snapshots (sku/name/price/supplier
         identity frozen at order time — never re-read after this).
    9.   status=PAYMENT_PENDING.
    10.  create the payment checkout — a pending Payment row recording
         which method the customer selected (`payment_method`, e.g.
         "crypto"/"ach"). No real processor is wired up yet, so this is
         an honest "we know what they intend to pay with" record, not a
         fabricated success.

    Fulfillment is deliberately NOT enqueued here — submit_supplier_order
    must only run once payment actually clears, which today means an
    admin calling app.services.payments.mark_order_paid (later: a real
    payment-provider webhook calling the same function). See that
    module's docstring for the full PAYMENT_PENDING -> PAID -> enqueue
    flow this order now enters.
    """
    if not consent.age_confirmed:
        raise StorefrontError("You must confirm you are at least 21 years old to place an order.")
    if not consent.ruo_acknowledged:
        raise StorefrontError("You must acknowledge the Research Use Only terms to place an order.")
    if not consent.terms_accepted:
        raise StorefrontError("You must agree to the Terms of Service and Privacy Policy to place an order.")

    lines, subtotal_cents = _resolve_and_price_items(session, items)

    country = shipping_address.get("country", "")
    shipping_quote = get_shipping_quote(session, country=country)
    tax_cents = calculate_tax_cents(session, subtotal_cents=subtotal_cents, shipping_address=shipping_address)
    total_cents = subtotal_cents + shipping_quote.amount_cents + tax_cents

    order = Order(
        public_order_number=_generate_public_order_number(),
        access_token=secrets.token_urlsafe(32),
        customer_email=email,
        customer_name=customer_name,
        customer_phone=customer_phone,
        status="PAYMENT_PENDING",
        shipping_address=shipping_address,
        subtotal_cents=subtotal_cents,
        shipping_cents=shipping_quote.amount_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        items=[
            OrderItem(
                product_variant_id=line.variant_id,
                sku_snapshot=line.sku,
                display_name_at_purchase=line.name,
                supplier_product_id_at_purchase=line.supplier_product_id,
                supplier_sku_at_purchase=line.supplier_sku,
                supplier_name_at_purchase=line.supplier_name,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                total_price_cents=line.total_price_cents,
                wholesale_cost_cents=line.wholesale_cost_cents,
            )
            for line in lines
        ],
    )
    session.add(order)
    session.flush()

    now = datetime.now(timezone.utc)
    session.add(
        ConsentRecord(
            order_id=order.id,
            age_acknowledged_at=now,
            ruo_acknowledged_at=now,
            ruo_terms_version=RUO_TERMS_VERSION,
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
        )
    )
    session.add(OrderEvent(order_id=order.id, event_type="created", data={"item_count": len(lines)}))
    payment = Payment(
        order_id=order.id,
        # provider records what the customer selected at checkout
        # ("crypto"/"ach"). For "crypto" (Speed), the checkout route
        # creates the Speed checkout session right after this and stamps
        # provider_payment_id + payment_instructions onto the order; if
        # that fails or the provider isn't configured yet, status simply
        # stays "pending" until app.services.payments.mark_order_paid
        # (admin action or a real webhook) confirms it actually cleared.
        provider=payment_method,
        status="pending",
        amount_cents=total_cents,
        currency="usd",
    )
    session.add(payment)
    # submit_supplier_order is deliberately NOT enqueued here — see this
    # function's docstring. It's enqueued by
    # app.services.payments.mark_order_paid once this order actually
    # transitions PAYMENT_PENDING -> PAID.
    session.flush()

    if payment_method == "crypto":
        _attach_crypto_instructions(session, order, payment)

    return order


def _attach_crypto_instructions(session: Session, order: Order, payment: Payment) -> None:
    """Create the Speed checkout session for a crypto order and attach the
    payment instructions as a transient attribute on the order
    (order.payment_instructions) for the checkout response.

    Deliberately degrades: any failure — provider not configured yet
    (blank SPEED_API_KEY), network trouble — is logged and swallowed.
    The order exists and stays PAYMENT_PENDING; the order page falls
    back to the manual "awaiting payment" note. Bitcoin payments
    activate the moment the key is configured, with zero further code
    changes.
    """
    from app.payments.registry import get_provider

    try:
        provider = get_provider("crypto")
        instructions = provider.create_payment_instructions(order)
    except Exception as exc:  # noqa: BLE001 — degraded checkout beats a failed one; see docstring
        logger.warning("Speed checkout session not created for order %s: %s", order.public_order_number, exc)
        return

    payment.provider_payment_id = instructions.details["provider_payment_id"]
    # Transient — not a column. order_response() picks it up only when
    # present (i.e. only in the POST /checkout/create response).
    order.payment_instructions = instructions  # type: ignore[attr-defined]
    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="payment_instructions_created",
            data={"provider": "crypto", "session_id": instructions.details["provider_payment_id"]},
        )
    )


def get_order_by_token(session: Session, token: str) -> Optional[Order]:
    return session.execute(select(Order).where(Order.access_token == token)).scalar_one_or_none()


def recreate_payment_instructions(session: Session, order: Order) -> Order:
    """Mint a fresh Speed checkout session for a still-unpaid crypto
    order, on the customer's explicit request (the order page's Pay
    button). The previous Payment row's session is superseded: a new
    pending Payment row is created for the new session so webhook
    correlation by provider_payment_id keeps working, and the new
    instructions ride back on order.payment_instructions exactly like
    checkout-create.

    Only valid for status=PAYMENT_PENDING crypto orders — a paid or
    failed order raises StorefrontError, and ACH never has hosted
    sessions at all.
    """
    if order.status != "PAYMENT_PENDING":
        raise StorefrontError("This order is not awaiting payment.")
    latest_payment = (
        session.execute(
            select(Payment)
            .where(Payment.order_id == order.id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    if latest_payment is None or latest_payment.provider != "crypto":
        raise StorefrontError("This order does not use hosted crypto checkout.")

    # Previous pending sessions are dead ends — mark them superseded so
    # nothing reads them as the active payment attempt.
    for old in session.execute(
        select(Payment).where(
            Payment.order_id == order.id,
            Payment.provider == "crypto",
            Payment.status == "pending",
        )
    ).scalars():
        old.status = "superseded"
        session.add(old)

    new_payment = Payment(
        order_id=order.id,
        provider="crypto",
        status="pending",
        amount_cents=order.total_cents,
        currency="usd",
    )
    session.add(new_payment)
    session.flush()
    _attach_crypto_instructions(session, order, new_payment)
    if not hasattr(order, "payment_instructions"):
        # Speed unconfigured / errored — nothing to pay with.
        raise StorefrontError("Bitcoin checkout is not available right now. Please try again later.")
    return order
