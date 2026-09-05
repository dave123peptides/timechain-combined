from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine

from worker.queue.provider import Job

metadata = sa.MetaData()

# Mirrors the `background_jobs` table defined by services/api's Alembic
# migrations — same hand-kept-in-sync-columns convention as
# supplier_sync/db.py's supplier_products_table, for the same reason (api
# and worker are separately deployed containers with no shared code
# layer today).
background_jobs_table = sa.Table(
    "background_jobs",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("job_type", sa.String(50), nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_error", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


class LocalQueueProvider:
    """Development QueueProvider, backed by Postgres — the same database
    api and worker already share, standing in for a real broker via the
    well-known "SELECT ... FOR UPDATE SKIP LOCKED" pattern.

    receive() atomically claims up to `max_messages` jobs that are either
    brand new (`status='pending'`) or were received before but never
    deleted and whose visibility timeout has since elapsed
    (`status='in_progress'` with `available_at` in the past) — that reuse
    of `available_at` for both "not yet due" and "visibility timeout" is
    what makes an undeleted job automatically retryable later without any
    separate expiry bookkeeping. SKIP LOCKED means two concurrent
    receive() calls (e.g. two worker replicas) never claim the same row.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enqueue(self, *, job_type: str, payload: dict[str, Any], delay_seconds: int = 0) -> None:
        values: dict[str, Any] = {"job_type": job_type, "payload": payload}
        if delay_seconds > 0:
            values["available_at"] = sa.text("now() + make_interval(secs => :delay_seconds)").bindparams(
                sa.bindparam("delay_seconds", value=delay_seconds, type_=sa.Integer)
            )
        with self._engine.begin() as conn:
            conn.execute(sa.insert(background_jobs_table).values(**values))

    def receive(self, *, max_messages: int = 10, visibility_timeout_seconds: int = 60) -> list[Job]:
        claimable = (
            sa.select(background_jobs_table.c.id)
            .where(
                background_jobs_table.c.status.in_(("pending", "in_progress")),
                background_jobs_table.c.available_at <= sa.func.now(),
            )
            .order_by(background_jobs_table.c.created_at)
            .limit(max_messages)
            .with_for_update(skip_locked=True)
        )
        new_available_at = sa.text("now() + make_interval(secs => :vis_seconds)").bindparams(
            sa.bindparam("vis_seconds", value=visibility_timeout_seconds, type_=sa.Integer)
        )
        stmt = (
            sa.update(background_jobs_table)
            .where(background_jobs_table.c.id.in_(claimable))
            .values(
                status="in_progress",
                attempts=background_jobs_table.c.attempts + 1,
                available_at=new_available_at,
                updated_at=sa.func.now(),
            )
            .returning(
                background_jobs_table.c.id,
                background_jobs_table.c.job_type,
                background_jobs_table.c.payload,
                background_jobs_table.c.attempts,
            )
        )
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()

        return [
            Job(
                id=row["id"],
                job_type=row["job_type"],
                payload=row["payload"],
                attempts=row["attempts"],
                receipt_handle=str(row["id"]),
            )
            for row in rows
        ]

    def delete(self, receipt_handle: str) -> None:
        job_id = uuid.UUID(receipt_handle)
        with self._engine.begin() as conn:
            conn.execute(sa.delete(background_jobs_table).where(background_jobs_table.c.id == job_id))
