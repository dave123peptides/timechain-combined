class OrderStatus:
    """Order.status values — a plain string column (no DB enum/CHECK
    constraint), so this is an application-level convention, not a
    schema constraint. Mirrored from services/api/app/models/order_status.py
    (worker and api share no code layer — see worker/db.py's docstring
    for the same convention applied to table shapes).

    Reachable today: PAYMENT_PENDING (set at order creation), PAID (set
    by api's app.services.payments.mark_order_paid — also what enqueues
    submit_supplier_order now, not order creation itself), PAYMENT_FAILED
    (set by mark_order_payment_failed), and MANUAL_REVIEW (set by
    submit_supplier_order on unrecoverable failure). The rest are not
    wired up yet by any code path — they're declared here so later work
    references one shared vocabulary instead of each phase inventing its
    own strings.
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
    submit attempt), SUPPLIER_ACCEPTED (AllianceTek accepted the order —
    set by submit_supplier_order on success), MANUAL_REVIEW (set on
    unrecoverable failure). AWAITING_SHIPMENT/SHIPPED are written by the
    tracking pipeline (Phase 1C — not built yet).
    """

    PENDING = "pending"
    SUPPLIER_ACCEPTED = "SUPPLIER_ACCEPTED"
    AWAITING_SHIPMENT = "AWAITING_SHIPMENT"
    SHIPPED = "SHIPPED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
