"""Worker entrypoint.

Long-polls the queue (LocalQueueProvider in dev, SQSQueueProvider in
production — see worker/queue/) and dispatches each received job to its
handler by job_type via JOB_HANDLERS (worker/jobs/). This is the only
place in the worker that runs continuously; individual handlers are
plain functions with no loop of their own, so they can be called
directly from tests without spinning up this loop.

A job that raises an *unexpected* exception is left in the queue (never
deleted) — it becomes receivable again once its visibility timeout
elapses, a generic fallback retry. Handlers that need bounded,
classified retry (e.g. submit_supplier_order's transient-vs-permanent
supplier-error handling — see worker/alliancetek/errors.py) instead
handle their own failure explicitly and never raise: they delete the
current delivery via a normal successful return and, if retrying,
enqueue a fresh delayed job themselves — that's why every handler
receives the QueueProvider, not just Engine.
"""

import logging
import time

from sqlalchemy import create_engine

from worker.config import get_settings
from worker.jobs import JOB_HANDLERS
from worker.queue import get_queue_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("timechain.worker")


def run() -> None:
    settings = get_settings()
    logger.info(
        "worker starting (environment=%s, queue_provider=%s)", settings.environment, settings.queue_provider
    )

    engine = create_engine(settings.database_url)
    queue = get_queue_provider(settings)
    # Visibility timeout is a multiple of the poll interval so a job that
    # fails outlives at least one full idle poll cycle before becoming
    # retryable again, rather than being reclaimed near-instantly.
    visibility_timeout_seconds = max(settings.worker_poll_interval_seconds * 6, 30)

    while True:
        try:
            jobs = queue.receive(max_messages=10, visibility_timeout_seconds=visibility_timeout_seconds)
        except Exception:
            # A transient DB/queue outage must not crash the process —
            # same "log and retry" posture as an individual job handler
            # failure below, just one level up. Without this, a brief
            # Postgres blip would kill the worker outright instead of
            # quietly waiting it out.
            logger.exception("worker: failed to receive jobs from queue; retrying after poll interval")
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        if not jobs:
            time.sleep(settings.worker_poll_interval_seconds)
            continue

        for job in jobs:
            handler = JOB_HANDLERS.get(job.job_type)
            if handler is None:
                logger.error(
                    "worker: no handler registered for job_type=%s (job_id=%s); leaving in queue for now",
                    job.job_type,
                    job.id,
                )
                continue
            try:
                handler(job.payload, engine, queue)
            except Exception:
                logger.exception(
                    "worker: job %s (job_type=%s, attempt=%s) failed; left in queue for retry",
                    job.id,
                    job.job_type,
                    job.attempts,
                )
                continue
            queue.delete(job.receipt_handle)
            logger.info("worker: job %s (job_type=%s) completed", job.id, job.job_type)


if __name__ == "__main__":
    run()
