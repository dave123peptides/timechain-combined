import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.shop import OrderResponse, ShippingAddressRequest, order_response
from app.core.config import get_settings
from app.db.session import get_db
from app.services import ghl_notify, order_notify, order_sheet, storefront
from app.services.order_export import order_notification_payload

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])

# Order-status page's Pay button lives here too — it mints a fresh
# hosted-checkout session for a still-unpaid order.
orders_router = APIRouter(prefix="/shop/orders", tags=["checkout"])


class CheckoutItemRequest(BaseModel):
    """Deliberately just these two fields — see
    app.services.storefront._resolve_and_price_items's docstring. Price,
    sellability, and mapping status are never accepted from the client;
    they're looked up fresh from the database on every call."""

    variant_id: uuid.UUID
    quantity: int = Field(gt=0)


class QuoteRequest(BaseModel):
    items: list[CheckoutItemRequest]
    country: str = "US"
    # Optional checkout discount code — validated and priced server-side
    # (app.constants.discount_codes); the client never sends an amount.
    discount_code: str | None = Field(default=None, max_length=40)


class QuoteLineResponse(BaseModel):
    variant_id: uuid.UUID
    name: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int


class QuoteResponse(BaseModel):
    items: list[QuoteLineResponse]
    subtotal_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    # The normalized code and cents off when the request's code is
    # valid; discount_error (and no discount) when it isn't — the quote
    # itself still succeeds so checkout can show the message inline.
    discount_code: str | None = None
    discount_cents: int = 0
    discount_error: str | None = None


class ConsentRequest(BaseModel):
    age_confirmed: bool
    ruo_acknowledged: bool
    terms_accepted: bool


class CreateCheckoutRequest(BaseModel):
    email: EmailStr
    # The full customer record (David, 9/4): manual fulfillment means a
    # person addresses the parcel and may need to reach the customer, so
    # both are required from the storefront.
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=7, max_length=40)
    shipping_address: ShippingAddressRequest
    items: list[CheckoutItemRequest]
    consent: ConsentRequest
    # What the customer says they'll pay with. Recorded on the Payment
    # row as `provider` at order-creation time. "venmo" and "zelle" are
    # the launch methods (David, 9/4): manual transfers the customer
    # sends themselves, matched to the order by its public order number
    # in the memo, then confirmed by an admin
    # (app.services.payments.mark_order_paid). "crypto" is Speed's hosted
    # Bitcoin checkout; "ach" still has no provider. The storefront only
    # offers the launch methods; the others stay accepted so existing
    # orders and the admin flow keep working.
    payment_method: Literal["venmo", "zelle", "crypto", "ach"]
    # Same code the quote validated; create_order re-validates and
    # re-prices it, and rejects the order outright if it isn't real.
    discount_code: str | None = Field(default=None, max_length=40)


@router.post("/quote", response_model=QuoteResponse)
def quote_checkout(body: QuoteRequest, db: Session = Depends(get_db)) -> QuoteResponse:
    """Read-only preview — writes nothing. All money returned in integer
    cents, computed entirely server-side from the database (variant
    price, is_sellable, supplier mapping status, the system_settings
    shipping rate); the request carries only variant_id/quantity, never
    a price. The actual charge is still always recomputed independently
    inside /checkout/create — this is display-only, same trust boundary
    as GET /shop/shipping-rate.
    """
    if not get_settings().checkout_enabled:
        raise HTTPException(status_code=503, detail="Checkout is currently unavailable.")
    try:
        quote = storefront.build_quote(
            db,
            items=[storefront.OrderItemRequest(variant_id=item.variant_id, quantity=item.quantity) for item in body.items],
            country=body.country,
            discount_code=body.discount_code,
        )
    except storefront.StorefrontError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QuoteResponse(
        items=[
            QuoteLineResponse(
                variant_id=line.variant_id,
                name=line.name,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                total_price_cents=line.total_price_cents,
            )
            for line in quote.items
        ],
        subtotal_cents=quote.subtotal_cents,
        shipping_cents=quote.shipping_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        discount_code=quote.discount_code,
        discount_cents=quote.discount_cents,
        discount_error=quote.discount_error,
    )


@router.post("/create", response_model=OrderResponse)
def create_checkout(
    body: CreateCheckoutRequest, background: BackgroundTasks, db: Session = Depends(get_db)
) -> OrderResponse:
    """Validates cart, products, and mappings; calculates totals
    server-side; validates shipping; records consent; creates the
    internal Order (UUID primary key) with a generated
    public_order_number and immutable OrderItem snapshots; sets
    status=PAYMENT_PENDING; and creates the pending Payment (checkout)
    row. See app.services.storefront.create_order for the full
    step-by-step. Nothing is written if any step fails.

    After the commit, the new-order notification (order_notify) runs as
    a background task so the response never waits on it.
    """
    if not get_settings().checkout_enabled:
        raise HTTPException(status_code=503, detail="Checkout is currently unavailable.")
    try:
        order = storefront.create_order(
            db,
            email=body.email,
            shipping_address=body.shipping_address.model_dump(),
            items=[
                storefront.OrderItemRequest(variant_id=item.variant_id, quantity=item.quantity)
                for item in body.items
            ],
            consent=storefront.ConsentInput(
                age_confirmed=body.consent.age_confirmed,
                ruo_acknowledged=body.consent.ruo_acknowledged,
                terms_accepted=body.consent.terms_accepted,
            ),
            payment_method=body.payment_method,
            customer_name=body.customer_name.strip(),
            customer_phone=body.customer_phone.strip(),
            discount_code=body.discount_code,
        )
        db.commit()
    except storefront.StorefrontError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(order)
    site = get_settings().public_site_url.rstrip("/")
    payload = order_notification_payload(order, order_url=f"{site}/order/{order.access_token}" if site else None)
    background.add_task(order_notify.notify_new_order, payload)
    background.add_task(order_sheet.append_order_row, payload)
    # GoHighLevel CRM push — customer-safe fields only (ghl_notify builds
    # them); skipped silently when GHL_ORDER_WEBHOOK_URL is blank.
    ghl = ghl_notify.ghl_payload(payload)
    if ghl:
        background.add_task(ghl_notify.push_order_to_ghl, ghl)
    return order_response(order)


@orders_router.post("/{token}/retry-payment", response_model=OrderResponse)
def retry_payment(token: str, db: Session = Depends(get_db)) -> OrderResponse:
    """Customer-initiated re-mint of the hosted crypto checkout session
    for a still-unpaid order (the order page's Pay button). Returns the
    order with fresh payment instructions — same shape as
    /checkout/create's response.
    """
    order = storefront.get_order_by_token(db, token)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    try:
        storefront.recreate_payment_instructions(db, order)
        db.commit()
    except storefront.StorefrontError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(order)
    return order_response(order)
