from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.events import WebhookEvent
from app.payments.registry import get_provider
from app.services import order_paid

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}")
async def receive_payment_webhook(
    provider: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
):
    """Inbound payment-provider webhooks. The provider named in the path
    must be registered in app/payments/registry.py ("bitcoin_opennode"
    for OpenNode); it verifies the signature and maps the event onto the
    order-state machine (app/payments/base.py).

    Idempotency: relies on WebhookEvent's UNIQUE(source, external_id)
    constraint. A provider's retried delivery of the same event hits the
    IntegrityError branch below and short-circuits to 200 without
    reprocessing — never a re-run of handle_event.

    If handle_event raises, nothing is committed (the WebhookEvent row
    included), FastAPI answers 500, and the provider's retry gets a
    clean second attempt — that is deliberate for transient failures
    such as OpenNode's paid re-check timing out.

    When handle_event reports that an order became PAID, the
    post-payment fan-out (sheet row + GHL, app/services/order_paid.py)
    runs as a background task after the commit — the same fan-out the
    admin Mark paid action triggers, so a webhook-confirmed order and a
    manually confirmed one look identical to staff.
    """
    try:
        payment_provider = get_provider(provider)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    raw_body = await request.body()

    try:
        event = payment_provider.verify_webhook(dict(request.headers), raw_body)
    except Exception as exc:  # noqa: BLE001 — any verification failure is an invalid webhook, not a server error
        raise HTTPException(status_code=400, detail=f"Webhook verification failed: {exc}") from exc

    webhook_event = WebhookEvent(
        source=provider,
        event_type=event.event_type,
        external_id=event.external_id,
        payload=event.raw,
        status="pending",
    )
    db.add(webhook_event)
    try:
        db.flush()
    except IntegrityError:
        # Already seen this exact (source, external_id) — a provider
        # retry, not a new event. Nothing to reprocess.
        db.rollback()
        return {"status": "already_processed"}

    paid_order_id = payment_provider.handle_event(db, event)
    webhook_event.status = "processed"
    webhook_event.processed_at = datetime.now(timezone.utc)
    db.commit()
    if paid_order_id is not None:
        background.add_task(order_paid.run_order_paid_fanout, paid_order_id)
    return {"status": "processed"}
