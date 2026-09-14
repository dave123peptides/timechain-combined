import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.constants.bulk_discounts import BULK_DISCOUNT_TIERS
from app.core.config import get_settings
from app.db.session import get_db
from app.services import storefront
from app.services.payments import display_payment

router = APIRouter(prefix="/shop", tags=["shop"])


class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    format: str
    # Raw form value ("lyophilized"/"preconstituted"/etc) — `format` above
    # is the display label; the frontend keys format-specific content
    # (reconstitution instructions vs. ready-to-use copy) off this instead.
    form: str | None
    strength: str | None
    price_cents: int


class CoaResponse(BaseModel):
    """One third-party Certificate of Analysis. `pdf_url` is the lab's
    own hosted copy and `verify_url` its verification page for
    `verify_code` — the customer checks the document with the lab, not
    with us. `tests` is the assay panel on the certificate (labels only,
    never results)."""

    model_config = ConfigDict(from_attributes=True)

    verify_code: str
    strength: str | None
    lot: str
    issued_on: date
    lab: str
    tests: list[str]
    pdf_url: str
    verify_url: str | None


class ProductSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str | None
    category: str | None
    images: list[str]
    starting_price_cents: int
    variants: list[VariantResponse]
    # Certificate rollup on the summary so the product-card badge and
    # /coa avoid an N+1 of detail fetches; the certificates themselves
    # are on the detail — see StorefrontProductSummary. 0 / null is the
    # honest "none held" state, rendered as "available on request".
    coa_count: int
    coa_latest_issued_on: date | None
    # Safety Data Sheet URL; null renders as "available on request".
    sds_url: str | None


class ProductFaqEntryResponse(BaseModel):
    q: str
    a: str


class ProductContentResponse(BaseModel):
    overview: str | None = None
    key_points: list[str] = []
    research_areas: list[str] = []
    # Slugs of other products worth cross-linking (e.g. a diluent, or a
    # complementary compound) — the frontend resolves these against the
    # live sellable catalog itself, so a slug that's out of stock or
    # renamed just silently drops rather than 404ing the page.
    pairs_with: list[str] = []
    faq: list[ProductFaqEntryResponse] = []


class ProductDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str | None
    category: str | None
    images: list[str]
    variants: list[VariantResponse]
    content: ProductContentResponse
    # Every published certificate, in Lab-report order (strength
    # ascending, newest first) — see StorefrontProductDetail.
    coas: list[CoaResponse]
    # See ProductSummaryResponse.
    sds_url: str | None


class CoaIndexEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    coas: list[CoaResponse]


class ShippingAddressRequest(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    region: str
    postal_code: str
    country: str


class ShippingRateResponse(BaseModel):
    country: str
    amount_cents: int


class OrderItemResponse(BaseModel):
    name: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int


class PaymentInstructionsResponse(BaseModel):
    """Present only in the POST /checkout/create response, and only when
    the payment provider actually produced instructions (e.g. a Speed
    charge for a crypto order). GET /shop/orders/{token} never re-creates
    charges, so it always returns null here — the order page shows the
    hosted-checkout link the customer already received at order time."""

    provider: str
    summary: str
    details: dict


class OrderResponse(BaseModel):
    # The only order identifier ever returned — orders.id (a UUID
    # database primary key) is never exposed. See
    # Order.public_order_number's docstring.
    public_order_number: str
    access_token: str
    status: str
    customer_email: str
    customer_name: str | None = None
    customer_phone: str | None = None
    shipping_address: dict | None
    subtotal_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    # Checkout discount code snapshot (normalized code + cents off the
    # subtotal); total_cents already reflects it.
    discount_code: str | None = None
    discount_cents: int = 0
    items: list[OrderItemResponse]
    created_at: datetime
    # The provider of the Payment row that describes this order ("venmo",
    # "zelle", "paypal", "bitcoin_opennode", "whop", "crypto", "ach") — the order page reads
    # it to show the right payment instructions after checkout and on
    # every later visit. See app.services.payments.display_payment for
    # which row that is when a hosted checkout was re-minted.
    payment_method: str | None = None
    # That row's status: pending | processing | underpaid | expired |
    # failed | superseded | succeeded. The order page uses it to tell a
    # Bitcoin customer "payment detected, waiting for confirmation" or
    # "the payment page expired, start a new one".
    payment_status: str | None = None
    # For a PAYMENT_PENDING hosted-checkout order: what the order page
    # needs to show the payment on every visit — for Bitcoin the
    # lightning_invoice, chain_address, bitcoin_uri, amount_sats,
    # expires_at and checkout_url; for PayPal the approve_url; for a Whop
    # card order the checkout_url behind its Pay Now button.
    # None once the order is paid/failed or the payment row is no longer
    # payable (expired/superseded), and for manual-transfer methods.
    payment_details: dict | None = None
    payment: PaymentInstructionsResponse | None = None


def latest_payment_method(order) -> str | None:
    """Provider of the Payment row that describes the order (the paid
    one if any, else the newest), or None for an order with no payment
    row at all (which create_order never produces, but the response must
    not 500 on a hand-edited database)."""
    payment = display_payment(order)
    return payment.provider if payment is not None else None


def latest_payment_status(order) -> str | None:
    payment = display_payment(order)
    return payment.status if payment is not None else None


_PAYABLE_STATUSES = ("pending", "processing", "underpaid")


def payable_payment_details(order) -> dict | None:
    """The stored provider_data of the payment the customer can still
    pay, or None."""
    if order.status != "PAYMENT_PENDING":
        return None
    payment = display_payment(order)
    if payment is None or payment.status not in _PAYABLE_STATUSES:
        return None
    return dict(payment.provider_data) if payment.provider_data else None


def order_response(order) -> OrderResponse:
    """Shared by GET /shop/orders/{token} and POST /api/v1/checkout/create
    (see app.api.checkout) — one place builds the customer-facing shape
    of an Order, so both call sites stay in sync.

    `payment` is populated only when create_order attached transient
    payment_instructions (a fresh checkout session) — i.e. only in the
    checkout-create response, never on the order-status page."""
    instructions = getattr(order, "payment_instructions", None)
    return OrderResponse(
        public_order_number=order.public_order_number,
        access_token=order.access_token,
        status=order.status,
        customer_email=order.customer_email,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        shipping_address=order.shipping_address,
        subtotal_cents=order.subtotal_cents,
        shipping_cents=order.shipping_cents,
        tax_cents=order.tax_cents,
        total_cents=order.total_cents,
        discount_code=order.discount_code,
        discount_cents=order.discount_cents or 0,
        items=[
            OrderItemResponse(
                name=item.display_name_at_purchase,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_price_cents=item.total_price_cents,
            )
            for item in order.items
        ],
        created_at=order.created_at,
        payment_method=latest_payment_method(order),
        payment_status=latest_payment_status(order),
        payment_details=payable_payment_details(order),
        payment=(
            PaymentInstructionsResponse(
                provider=instructions.provider,
                summary=instructions.summary,
                details=instructions.details,
            )
            if instructions is not None
            else None
        ),
    )


class ShopFilterOptionsResponse(BaseModel):
    categories: list[str]
    formats: list[str]


class BulkDiscountTierResponse(BaseModel):
    min_quantity: int
    percent_off: int


@router.get("/products", response_model=list[ProductSummaryResponse])
def list_products(
    category: str | None = Query(default=None),
    form: str | None = Query(default=None, alias="format"),
    q: str | None = Query(default=None, max_length=100),
    # Deliberately `str | None` and not a Literal: an unrecognized value
    # falls back to name order in the service layer rather than 422ing.
    # This is a public catalog page reached by hand-typed and stale
    # bookmarked URLs; a typo'd sort key must not error the page.
    sort: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[storefront.StorefrontProductSummary]:
    # CHECKOUT_ENABLED=false: present an empty storefront rather than a
    # 503 — a go-live safety switch, not an outage, so it should look
    # like "nothing for sale yet," not "something is broken."
    if not get_settings().checkout_enabled:
        return []
    return storefront.list_sellable_products(db, category=category, form=form, q=q, sort=sort)


@router.get("/filter-options", response_model=ShopFilterOptionsResponse)
def get_filter_options(db: Session = Depends(get_db)) -> ShopFilterOptionsResponse:
    """Distinct category/format values actually present in the sellable
    catalog right now — the shop page's filter UI derives its options
    from this rather than any hardcoded list, so it stays correct
    regardless of what the real catalog ends up using."""
    if not get_settings().checkout_enabled:
        return ShopFilterOptionsResponse(categories=[], formats=[])
    categories, formats = storefront.list_sellable_filter_options(db)
    return ShopFilterOptionsResponse(categories=categories, formats=formats)


@router.get("/bulk-discount-tiers", response_model=list[BulkDiscountTierResponse])
def get_bulk_discount_tiers() -> list[BulkDiscountTierResponse]:
    """Read-only — the frontend uses this to render a "buy more, save
    more" table without hardcoding percentages that could drift from
    what checkout actually charges (see app.services.storefront's use of
    the same BULK_DISCOUNT_TIERS to compute the real price)."""
    return [
        BulkDiscountTierResponse(min_quantity=tier.min_quantity, percent_off=tier.percent_off)
        for tier in sorted(BULK_DISCOUNT_TIERS, key=lambda t: t.min_quantity)
    ]


@router.get("/products/{slug}", response_model=ProductDetailResponse)
def get_product(slug: str, db: Session = Depends(get_db)) -> storefront.StorefrontProductDetail:
    if not get_settings().checkout_enabled:
        raise HTTPException(status_code=404, detail="Product not found.")
    product = storefront.get_sellable_product_by_slug(db, slug)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.get("/coas", response_model=list[CoaIndexEntryResponse])
def list_coas(db: Session = Depends(get_db)) -> list[storefront.StorefrontCoaIndexEntry]:
    """Every published certificate for every sellable product, grouped
    by product — /coa's one call. Products holding no certificate are
    absent here; the page lists them as "on request" from
    GET /shop/products instead."""
    if not get_settings().checkout_enabled:
        return []
    return storefront.list_published_coas(db)


@router.get("/shipping-rate", response_model=ShippingRateResponse)
def get_shipping_rate(db: Session = Depends(get_db)) -> ShippingRateResponse:
    """For display before checkout is submitted — the real charge is
    always recomputed inside create_order regardless of what this
    returns, same as price."""
    if not get_settings().checkout_enabled:
        raise HTTPException(status_code=503, detail="Checkout is currently unavailable.")
    try:
        quote = storefront.get_shipping_quote(db)
    except storefront.StorefrontError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ShippingRateResponse(country=quote.country, amount_cents=quote.amount_cents)


@router.get("/orders/{token}", response_model=OrderResponse)
def get_order(token: str, db: Session = Depends(get_db)) -> OrderResponse:
    order = storefront.get_order_by_token(db, token)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order_response(order)
