"""ORM models.

Importing this package registers every table on `Base.metadata`. Alembic's
`env.py` imports it so `--autogenerate` can see the full schema, and it's
the single place to import from when you need a model class.
"""

from app.models.catalog import (
    Product,
    ProductCoa,
    ProductVariant,
    SupplierProduct,
    SupplierProductMapping,
)
from app.models.events import AuditEvent, ConsentRecord, WebhookEvent
from app.models.fulfillment import (
    Shipment,
    SupplierAttempt,
    SupplierOrder,
    TrackingEvent,
)
from app.models.jobs import BackgroundJob
from app.models.orders import Order, OrderEvent, OrderItem
from app.models.payments import Payment, PaymentEvent, Refund
from app.models.settings import SystemSetting

__all__ = [
    "Product",
    "ProductCoa",
    "ProductVariant",
    "SupplierProduct",
    "SupplierProductMapping",
    "Order",
    "OrderItem",
    "OrderEvent",
    "Payment",
    "PaymentEvent",
    "Refund",
    "SupplierOrder",
    "SupplierAttempt",
    "Shipment",
    "TrackingEvent",
    "WebhookEvent",
    "ConsentRecord",
    "SystemSetting",
    "AuditEvent",
    "BackgroundJob",
]
