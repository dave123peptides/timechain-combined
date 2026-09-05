from __future__ import annotations

from sqlalchemy import create_engine

from worker.config import Settings
from worker.queue.local import LocalQueueProvider
from worker.queue.provider import Job, QueueProvider
from worker.queue.sqs import SQSQueueProvider

__all__ = ["Job", "QueueProvider", "get_queue_provider"]


def get_queue_provider(settings: Settings) -> QueueProvider:
    """The only place worker code should ever choose between Local and
    SQS — everything else (main.py's dispatch loop, job handlers that
    enqueue follow-up work) depends on QueueProvider and never checks
    settings.queue_provider itself."""
    if settings.queue_provider == "sqs":
        return SQSQueueProvider(queue_url=settings.sqs_queue_url, region=settings.aws_region)
    if settings.queue_provider == "local":
        engine = create_engine(settings.database_url)
        return LocalQueueProvider(engine)
    raise ValueError(f"Unknown queue_provider={settings.queue_provider!r}; expected 'local' or 'sqs'.")
