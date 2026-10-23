import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.db.session import get_db
from app.services import order_requests

router = APIRouter(prefix="/api/v1/order-requests", tags=["order-requests"])
admin_router = APIRouter(prefix="/admin/order-requests", tags=["admin"], dependencies=[Depends(require_admin_auth)])


class OrderRequestItemRequest(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(gt=0, le=order_requests.MAX_QUANTITY)


class CreateOrderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    organization: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)
    items: list[OrderRequestItemRequest] = Field(min_length=1, max_length=order_requests.MAX_ITEMS)
    source_path: str | None = Field(default=None, max_length=300)
    # Honeypot: the storefront renders this field hidden and leaves it
    # empty. Anything in it is a bot; the request is dropped but answered
    # with the same shape so the bot learns nothing.
    website: str | None = Field(default=None, max_length=300)


class OrderRequestItemResponse(BaseModel):
    variant_id: str
    sku: str
    product_slug: str
    product_name: str
    variant_name: str
    form: str | None
    form_label: str
    strength: str | None
    quantity: int


class OrderRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference: str
    created_at: datetime


class AdminOrderRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    status: str
    created_at: datetime
    contact_name: str
    organization: str
    role: str | None
    email: str
    phone: str | None
    region: str | None
    notes: str | None
    items: list[OrderRequestItemResponse]
    source_path: str | None


@router.post("", response_model=OrderRequestResponse, status_code=201)
def create(body: CreateOrderRequest, background: BackgroundTasks, db: Session = Depends(get_db)) -> OrderRequestResponse:
    """Store the request and forward it to the CRM webhook. Public: this
    is the site's one conversion, and it never involves money."""
    if body.website:
        # Honeypot tripped: pretend it worked.
        return OrderRequestResponse(reference="REQ-RECEIVED", created_at=datetime.now().astimezone())
    try:
        request = order_requests.create_order_request(
            db,
            contact=order_requests.ContactInput(
                name=body.name,
                organization=body.organization,
                email=str(body.email),
                role=body.role,
                phone=body.phone,
                region=body.region,
                notes=body.notes,
                source_path=body.source_path,
            ),
            items=[order_requests.RequestedItem(variant_id=item.variant_id, quantity=item.quantity) for item in body.items],
        )
    except order_requests.OrderRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background.add_task(order_requests.forward_order_request, order_requests.webhook_payload(request))
    return OrderRequestResponse(reference=request.reference, created_at=request.created_at)


@admin_router.get("", response_model=list[AdminOrderRequestResponse])
def admin_list(db: Session = Depends(get_db)):
    return order_requests.list_order_requests(db)
