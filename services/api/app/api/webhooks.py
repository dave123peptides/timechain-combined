from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.events import WebhookEvent
from app.payments.registry import get_provider

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}")
async def receive_payment_webhook(provider: str, request: Request, db: Session = Depends(get_db)):
    """Inert until a real crypto/ACH provider is registered in
    app/payments/registry.py — see that module and app/payments/base.py
    for why. The shape exists now so integrating a real provider later
    is "implement PaymentProvider," not "invent webhook plumbing."

    Idempotency: relies on WebhookEvent's UNIQUE(source, external_id)
    constraint. A provider's retried delivery of the same event hits the
    IntegrityError branch below and short-circuits to 200 without
    reprocessing — never a re-run of handle_event.
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

    payment_provider.handle_event(db, event)
    webhook_event.status = "processed"
    webhook_event.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "processed"}
