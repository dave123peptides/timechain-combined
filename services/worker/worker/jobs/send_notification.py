from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.engine import Engine

from worker.alliancetek.client import AllianceTekClient
from worker.queue.provider import QueueProvider

logger = logging.getLogger("timechain.worker.jobs.send_notification")


def handle(
    payload: dict[str, Any], engine: Engine, queue: QueueProvider, *, client: Optional[AllianceTekClient] = None
) -> None:
    """job_type="send_notification".

    No email/SMS provider is configured anywhere in this project yet —
    this is a real, honest placeholder (not a fabricated "sent"), same
    posture as Payment.provider="not_configured" and SQSQueueProvider
    before a real queue exists. `engine`/`client`/`queue` are accepted
    only for signature parity with the other job handlers (see
    worker/jobs/__init__.py's JOB_HANDLERS) — this handler uses none of
    them.
    """
    logger.info("send_notification: no notification provider configured; not sent. payload=%r", payload)
