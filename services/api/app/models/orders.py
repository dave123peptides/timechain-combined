import uuid
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    # The only order identifier ever shown to a customer or exposed by
    # the API — orders.id (a UUID, internal-only) is never returned to
    # the frontend. Format "TCP-XXXXXX" (see
    # app.services.storefront._generate_public_order_number).
    public_order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    # Opaque, unguessable — the only "auth" for the guest order-lookup
    # page (/order/[token]). Deliberately not public_order_number:
    # that's the human/support-facing reference a customer might read
    # aloud, this is what's actually in the URL.
    access_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    # The name the parcel is addressed to and a contact number — required
    # at checkout since manual fulfillment (David, 9/4): an admin places
    # the order with the supplier by hand from these. Nullable only for
    # orders created before the columns existed.
    customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PAYMENT_PENDING", server_default="PAYMENT_PENDING"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd", server_default="usd")
    # line1/line2/city/region/postal_code/country — kept as JSONB rather
    # than individual columns, matching this schema's existing habit for
    # flexible structured data (Product.images, *.data columns).
    shipping_address: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Integer cents — never float — for every money column in this schema.
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    shipping_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderEvent"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")
    supplier_orders: Mapped[list["SupplierOrder"]] = relationship(back_populates="order")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")
    consent_records: Mapped[list["ConsentRecord"]] = relationship(back_populates="order")


class OrderItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A line item on an order — an immutable purchase-time snapshot.
    Every field here is copied at order-creation time from
    ProductVariant/SupplierProduct/SupplierProductMapping and never
    updated afterward (this model only has CreatedAtMixin, not
    TimestampMixin — no updated_at, matching this schema's existing
    append-only convention for OrderEvent/TrackingEvent/etc.). Fulfillment
    (see worker/alliancetek/payload.py) reads exclusively from these
    columns, never from a live join — a later catalog edit, supplier
    rename, or remapping must never change what an already-placed order
    says it bought or what gets submitted to the supplier for it.
    """

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name_at_purchase: Mapped[str] = mapped_column(String(255), nullable=False)
    # The supplier identity backing this line item, frozen at purchase
    # time — a later remap, rename, or the supplier product disappearing
    # entirely must never change what this order item says was ordered.
    # supplier_product_id_at_purchase is AllianceTek's own numeric id
    # (matches SupplierProduct.supplier_product_id), not a local FK —
    # deliberately not a foreign key, for the same reason
    # SupplierProductMapping's snapshot fields aren't: it must survive
    # the referenced supplier_products row changing or even, in
    # principle, no longer resolving.
    supplier_product_id_at_purchase: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_sku_at_purchase: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_name_at_purchase: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable — ProductVariant.wholesale_cost_cents itself is nullable
    # (not every variant has a recorded wholesale cost).
    wholesale_cost_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
    product_variant: Mapped["ProductVariant"] = relationship(back_populates="order_items")


class OrderEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail of what happened to an order (status
    changes, notes, etc.)."""

    __tablename__ = "order_events"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="events")
