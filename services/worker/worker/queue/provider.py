from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Job:
    """One unit of background work, as handed to a job handler.

    `receipt_handle` is opaque to callers — it identifies *this specific
    delivery* of the job, not the job itself, mirroring SQS: pass it
    straight through to `delete()` once the job has been handled
    successfully. Never construct a Job by hand outside a QueueProvider
    implementation.
    """

    id: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    attempts: int
    receipt_handle: str


class QueueProvider(Protocol):
    """Everything business logic (worker/main.py's dispatch loop, and
    api's app/services/queue.py) should ever depend on for background
    work — never boto3 directly, and never a raw SQL query against
    background_jobs outside this package. LocalQueueProvider and
    SQSQueueProvider are interchangeable implementations of this same
    interface; get_queue_provider() in __init__.py picks one based on
    settings.queue_provider.
    """

    def enqueue(self, *, job_type: str, payload: dict[str, Any], delay_seconds: int = 0) -> None:
        """Submits a new job, optionally not receivable until
        `delay_seconds` from now. Job handlers use this to implement
        bounded retry-with-backoff for transient failures — e.g.
        submit_supplier_order re-enqueues itself with an increasing
        delay per AllianceTek's retry schedule rather than sleeping
        in-process (a 30-minute delay would otherwise block the worker
        on a single job). Not called by the API in practice today (it
        enqueues directly via its own background_jobs insert, in the
        same transaction as the work that triggered it — see
        app/services/queue.py)."""
        ...

    def receive(self, *, max_messages: int = 10, visibility_timeout_seconds: int = 60) -> list[Job]:
        """Returns up to `max_messages` jobs currently available to work
        on. A received job becomes invisible to other receivers until
        either `delete()` is called for it or `visibility_timeout_seconds`
        elapses — whichever comes first. Never returns the same
        undeleted, still-invisible job to two concurrent receivers."""
        ...

    def delete(self, receipt_handle: str) -> None:
        """Acknowledges a job as done, using the receipt_handle from the
        Job it came from. Only call this after the job has actually
        succeeded — a job left un-deleted becomes receivable again once
        its visibility timeout elapses, which is the retry mechanism."""
        ...
