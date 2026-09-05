import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class WebhookEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Raw inbound webhook payloads from external systems (payment
    provider, carriers, suppliers), kept for idempotency and replay."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_webhook_events_source_external_id"),
    )

    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentRecord(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The checkout-time consent capture for one order — age (21+),
    Research Use Only, and terms/privacy, all acknowledged together as
    part of placing the order. One row per order (not nullable, not
    reused across orders): this is deliberately not a generic consent
    log — see app.services.storefront.create_order, which creates this
    in the same flush as the Order/OrderItems and refuses to create an
    order at all if any of the three wasn't affirmatively given.

    This is separate from, and never satisfied by, the site-entry age
    attestation cookie — that's a different, earlier acknowledgment;
    checkout requires its own.
    """

    __tablename__ = "consent_records"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    age_acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ruo_acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Which version of each document was in effect when the customer
    # agreed — stamped by the backend from its own constants (see
    # app.services.storefront), never taken from the client.
    ruo_terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(20), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="consent_records")


class AuditEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only log of administrative/system actions, independent of
    any single entity type."""

    __tablename__ = "audit_events"

    actor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
