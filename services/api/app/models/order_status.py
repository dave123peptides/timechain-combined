class OrderStatus:
    """Order.status values — a plain string column (no DB enum/CHECK
    constraint), so this is an application-level convention, not a
    schema constraint. Mirrored in services/worker/worker/order_status.py
    (api and worker share no code layer today).

    Reachable today: PAYMENT_PENDING (set at order creation), PAID (set
    by app.services.payments.mark_order_paid — an admin action today,
    a real payment-provider webhook later — which is also what enqueues
    submit_supplier_order; order creation itself no longer enqueues it),
    PAYMENT_FAILED (set by mark_order_payment_failed), and MANUAL_REVIEW
    (set by the worker's submit_supplier_order job on unrecoverable
    failure — see worker/jobs/submit_supplier_order.py). The rest are
    not wired up yet by any code path — they're declared here so later
    work (reconciliation, admin UI, settings) references one shared
    vocabulary instead of each phase inventing its own strings.
    """

    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    FULFILLMENT_QUEUED = "FULFILLMENT_QUEUED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class SupplierOrderStatus:
    """SupplierOrder.status values — same free-form-string convention as
    OrderStatus above.

    Reachable today: pending (the column default, before the first
    submit attempt), SUPPLIER_ACCEPTED (AllianceTek accepted the order),
    MANUAL_REVIEW (unrecoverable failure). AWAITING_SHIPMENT/SHIPPED are
    written by the tracking pipeline (Phase 1C — not built yet).
    """

    PENDING = "pending"
    SUPPLIER_ACCEPTED = "SUPPLIER_ACCEPTED"
    AWAITING_SHIPMENT = "AWAITING_SHIPMENT"
    SHIPPED = "SHIPPED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
