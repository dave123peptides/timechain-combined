from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.engine import Engine

from worker.jobs import reconcile_order, refresh_tracking, send_notification, submit_supplier_order
from worker.queue.provider import QueueProvider

JobHandler = Callable[[dict[str, Any], Engine, QueueProvider], None]

# The single dispatch table worker/main.py's poll loop uses to route a
# received Job to its handler by job_type. Adding a new job type means
# adding one module here plus one entry — never a growing if/elif chain
# in main.py.
JOB_HANDLERS: dict[str, JobHandler] = {
    "submit_supplier_order": submit_supplier_order.handle,
    "refresh_tracking": refresh_tracking.handle,
    "reconcile_order": reconcile_order.handle,
    "send_notification": send_notification.handle,
}

__all__ = ["JOB_HANDLERS", "JobHandler"]
