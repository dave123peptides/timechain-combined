from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = sa.MetaData()

# Mirrors tables defined by services/api's Alembic migrations. Defined
# here rather than imported because services/api and services/worker are
# separately deployed containers with no shared code layer today — same
# convention as supplier_sync/db.py's supplier_products_table.

orders_table = sa.Table(
    "orders",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("public_order_number", sa.String(50), nullable=False),
    sa.Column("access_token", sa.String(64), nullable=False),
    sa.Column("customer_email", sa.String(320), nullable=False),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("currency", sa.String(3), nullable=False),
    sa.Column("shipping_address", JSONB, nullable=True),
    sa.Column("subtotal_cents", sa.Integer, nullable=False),
    sa.Column("shipping_cents", sa.Integer, nullable=False),
    sa.Column("tax_cents", sa.Integer, nullable=False),
    sa.Column("total_cents", sa.Integer, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

supplier_products_table = sa.Table(
    "supplier_products",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("supplier_product_id", sa.BigInteger, nullable=False),
    sa.Column("supplier_key", sa.String(20), nullable=False),
)

order_items_table = sa.Table(
    "order_items",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("product_variant_id", UUID(as_uuid=True), nullable=False),
    sa.Column("sku_snapshot", sa.String(100), nullable=False),
    sa.Column("display_name_at_purchase", sa.String(255), nullable=False),
    sa.Column("supplier_product_id_at_purchase", sa.BigInteger, nullable=False),
    sa.Column("supplier_sku_at_purchase", sa.Text, nullable=False),
    sa.Column("supplier_name_at_purchase", sa.Text, nullable=False),
    sa.Column("quantity", sa.Integer, nullable=False),
    sa.Column("unit_price_cents", sa.Integer, nullable=False),
    sa.Column("total_price_cents", sa.Integer, nullable=False),
    sa.Column("wholesale_cost_cents", sa.Integer, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

order_events_table = sa.Table(
    "order_events",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("event_type", sa.String(50), nullable=False),
    sa.Column("data", JSONB, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

supplier_orders_table = sa.Table(
    "supplier_orders",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("supplier_order_number", sa.String(50), nullable=False),
    sa.Column("provider", sa.String(50), nullable=False),
    sa.Column("supplier_key", sa.String(20), nullable=True),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("cost_cents", sa.Integer, nullable=True),
    sa.Column("currency", sa.String(3), nullable=False),
    sa.Column("external_reference", sa.String(255), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

supplier_attempts_table = sa.Table(
    "supplier_attempts",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("supplier_order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("attempt_number", sa.Integer, nullable=False),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Column("response_data", JSONB, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

shipments_table = sa.Table(
    "shipments",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("order_id", UUID(as_uuid=True), nullable=False),
    sa.Column("carrier", sa.String(100), nullable=True),
    sa.Column("tracking_number", sa.String(255), nullable=True),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

tracking_events_table = sa.Table(
    "tracking_events",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("shipment_id", UUID(as_uuid=True), nullable=False),
    sa.Column("status", sa.String(50), nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("raw_data", JSONB, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
