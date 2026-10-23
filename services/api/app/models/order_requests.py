import uuid
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class OrderRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A multi-quantity order request from the storefront (David,
    2026-10-22: the site takes no payments; a research organization or
    practice builds a list of compounds, formats, strengths and
    quantities and sends it with their contact details, and the order is
    arranged from there). Append-only, like OrderItem: `items` is a
    snapshot of what was asked for at the time, never a live join, so a
    later catalog change can't rewrite a request."""

    __tablename__ = "order_requests"

    # The only identifier shown to the requester or the CRM: "REQ-XXXXXX".
    reference: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEW", server_default="NEW")

    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # [{variant_id, sku, product_slug, product_name, form, strength,
    #   quantity}, ...] as validated against the sellable catalog at
    # submission time.
    items: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Where the requester was on the site when they sent it (the page
    # path), for context in the CRM. Never used for anything else.
    source_path: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
