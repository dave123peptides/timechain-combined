import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.db.session import get_db
from app.services import admin_orders, admin_products
from app.services.order_export import list_export_rows, rows_to_csv

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_auth)])


class AdminProductRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variant_id: uuid.UUID
    timechain_product: str
    format: str
    strength: str | None
    wholesale_cost_cents: int | None
    retail_price_cents: int
    sellable: bool
    supplier_product_id: int | None
    supplier_sku: str | None
    supplier_name: str | None
    confidence: str | None
    mapping_status: str


class SupplierProductOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supplier_product_id: int
    supplier_sku: str
    supplier_name: str


class MappingActionRequest(BaseModel):
    supplier_product_id: int
    actor: str


class ActorOnlyRequest(BaseModel):
    actor: str


@router.get("/products", response_model=list[AdminProductRowResponse])
def list_products(db: Session = Depends(get_db)) -> list[admin_products.AdminProductRow]:
    return admin_products.list_admin_products(db)


@router.get("/supplier-products", response_model=list[SupplierProductOptionResponse])
def list_supplier_products(db: Session = Depends(get_db)) -> list[admin_products.SupplierProductOption]:
    return admin_products.list_supplier_product_options(db)


@router.post("/products/{variant_id}/approve", response_model=AdminProductRowResponse | None)
def approve_mapping(variant_id: uuid.UUID, body: MappingActionRequest, db: Session = Depends(get_db)):
    try:
        admin_products.set_mapping(
            db,
            variant_id=variant_id,
            supplier_product_id=body.supplier_product_id,
            actor=body.actor,
            action_label="mapping.approved",
        )
        db.commit()
    except admin_products.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_row(db, variant_id)


@router.post("/products/{variant_id}/change", response_model=AdminProductRowResponse | None)
def change_mapping(variant_id: uuid.UUID, body: MappingActionRequest, db: Session = Depends(get_db)):
    try:
        admin_products.set_mapping(
            db,
            variant_id=variant_id,
            supplier_product_id=body.supplier_product_id,
            actor=body.actor,
            action_label="mapping.changed",
        )
        db.commit()
    except admin_products.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_row(db, variant_id)


@router.post("/products/{variant_id}/unmap", response_model=AdminProductRowResponse | None)
def unmap_variant(variant_id: uuid.UUID, body: ActorOnlyRequest, db: Session = Depends(get_db)):
    try:
        admin_products.unmap(db, variant_id=variant_id, actor=body.actor)
        db.commit()
    except admin_products.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_row(db, variant_id)


@router.post("/products/{variant_id}/enable", response_model=AdminProductRowResponse | None)
def enable_variant(variant_id: uuid.UUID, body: ActorOnlyRequest, db: Session = Depends(get_db)):
    try:
        admin_products.enable(db, variant_id=variant_id, actor=body.actor)
        db.commit()
    except admin_products.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_row(db, variant_id)


@router.post("/products/{variant_id}/disable", response_model=AdminProductRowResponse | None)
def disable_variant(variant_id: uuid.UUID, body: ActorOnlyRequest, db: Session = Depends(get_db)):
    try:
        admin_products.disable(db, variant_id=variant_id, actor=body.actor)
        db.commit()
    except admin_products.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_row(db, variant_id)


def _find_row(db: Session, variant_id: uuid.UUID) -> admin_products.AdminProductRow | None:
    """Re-reads the single updated row after an action, so the frontend
    can patch its table in place instead of refetching all ~164 rows."""
    for row in admin_products.list_admin_products(db):
        if row.variant_id == variant_id:
            return row
    return None


class AdminOrderRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    public_order_number: str
    customer_email: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    total_cents: int
    currency: str
    created_at: str
    payment_provider: Optional[str]
    payment_status: Optional[str]


class AdminOrderItemDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name_at_purchase: str
    sku_snapshot: str
    supplier_sku_at_purchase: str
    supplier_name_at_purchase: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int


class AdminPaymentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_payment_id: Optional[str]
    status: str
    amount_cents: int
    events: list[dict]


class AdminOrderDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    public_order_number: str
    customer_email: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: str
    shipping_address: Optional[dict]
    subtotal_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    created_at: str
    items: list[AdminOrderItemDetailResponse]
    payments: list[AdminPaymentDetailResponse]
    events: list[dict]


class MarkOrderPaidRequest(BaseModel):
    actor: str
    provider: str
    provider_payment_id: Optional[str] = None
    note: Optional[str] = None


class MarkOrderPaymentFailedRequest(BaseModel):
    actor: str
    reason: str


@router.get("/orders", response_model=list[AdminOrderRowResponse])
def list_orders(db: Session = Depends(get_db)) -> list[admin_orders.AdminOrderRow]:
    return admin_orders.list_admin_orders(db)


@router.get("/orders/export.csv")
def export_orders_csv(
    status: str | None = Query(default=None, description="Only orders in this status, e.g. PAID"),
    db: Session = Depends(get_db),
) -> Response:
    """Every order as one spreadsheet row — customer, address, items
    with supplier SKUs, totals, payment method/status. The manual
    fulfillment worksheet (David, 9/4): open in Excel / Sheets, place
    the paid rows with the supplier. See app/services/order_export.py.
    """
    csv_text = rows_to_csv(list_export_rows(db, status=status))
    suffix = f"-{status.lower()}" if status else ""
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="timechain-orders{suffix}.csv"'},
    )


@router.get("/orders/{order_id}", response_model=AdminOrderDetailResponse)
def get_order_detail(order_id: uuid.UUID, db: Session = Depends(get_db)):
    detail = admin_orders.get_admin_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="No such order.")
    return detail


@router.post("/orders/{order_id}/mark-paid", response_model=AdminOrderRowResponse | None)
def mark_order_paid(order_id: uuid.UUID, body: MarkOrderPaidRequest, db: Session = Depends(get_db)):
    try:
        admin_orders.admin_mark_order_paid(
            db,
            order_id=order_id,
            actor=body.actor,
            provider=body.provider,
            provider_payment_id=body.provider_payment_id,
            note=body.note,
        )
        db.commit()
    except admin_orders.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_order_row(db, order_id)


@router.post("/orders/{order_id}/mark-payment-failed", response_model=AdminOrderRowResponse | None)
def mark_order_payment_failed(order_id: uuid.UUID, body: MarkOrderPaymentFailedRequest, db: Session = Depends(get_db)):
    try:
        admin_orders.admin_mark_order_payment_failed(db, order_id=order_id, actor=body.actor, reason=body.reason)
        db.commit()
    except admin_orders.AdminActionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _find_order_row(db, order_id)


def _find_order_row(db: Session, order_id: uuid.UUID) -> admin_orders.AdminOrderRow | None:
    for row in admin_orders.list_admin_orders(db):
        if row.order_id == order_id:
            return row
    return None
