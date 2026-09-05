import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd", server_default="usd")

    order: Mapped["Order"] = relationship(back_populates="payments")
    events: Mapped[list["PaymentEvent"]] = relationship(back_populates="payment", cascade="all, delete-orphan")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment", cascade="all, delete-orphan")


class PaymentEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only log of provider webhook/state events for a payment.
    `provider_event_id` gives webhook handlers an idempotency key."""

    __tablename__ = "payment_events"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    payment: Mapped["Payment"] = relationship(back_populates="events")


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd", server_default="usd")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    provider_refund_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    payment: Mapped["Payment"] = relationship(back_populates="refunds")
