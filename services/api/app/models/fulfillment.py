import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SupplierOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A purchase placed with a supplier to fulfill a customer order.

    One row per (order, provider) — AllianceTek's real order API takes a
    single orderNumber with an items array, not one submission per
    product, so this no longer points at a single supplier_products row.
    supplier_order_number is set once at creation and always equals
    order.public_order_number; every retry reuses it unchanged (that
    reuse is what makes the AllianceTek submission idempotent — see
    worker/jobs/submit_supplier_order.py).
    """

    __tablename__ = "supplier_orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="alliancetek", server_default="alliancetek")
    # Which pharmacy account the order was pushed to (umsrx / nxgen),
    # resolved at push time from the mapped supplier_products row. NULL
    # for pre-dual-supplier orders; tracking/reconcile fall back to the
    # default client for those.
    supplier_key: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    cost_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd", server_default="usd")
    external_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="supplier_orders")
    attempts: Mapped[list["SupplierAttempt"]] = relationship(
        back_populates="supplier_order", cascade="all, delete-orphan"
    )


class SupplierAttempt(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One attempt (of possibly several, for retry/backoff) to place a
    supplier order."""

    __tablename__ = "supplier_attempts"
    __table_args__ = (
        UniqueConstraint(
            "supplier_order_id", "attempt_number", name="uq_supplier_attempts_supplier_order_attempt_number"
        ),
    )

    supplier_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    supplier_order: Mapped["SupplierOrder"] = relationship(back_populates="attempts")


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    carrier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="shipments")
    tracking_events: Mapped[list["TrackingEvent"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )


class TrackingEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only carrier tracking history for a shipment."""

    __tablename__ = "tracking_events"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    shipment: Mapped["Shipment"] = relationship(back_populates="tracking_events")
