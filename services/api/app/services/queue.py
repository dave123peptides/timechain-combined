from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.jobs import BackgroundJob


def enqueue_job(session: Session, *, job_type: str, payload: dict) -> BackgroundJob:
    """Hand a unit of background work to the worker.

    Just an insert into background_jobs, participating in the caller's
    existing transaction (see create_order — the job is only ever
    visible if the surrounding commit that created it also succeeds).
    api only ever enqueues; it never receives or deletes jobs, so it
    doesn't need the full QueueProvider abstraction the worker has (see
    worker/queue/) — that exists worker-side, where jobs are actually
    consumed.
    """
    job = BackgroundJob(job_type=job_type, payload=payload)
    session.add(job)
    session.flush()
    return job
