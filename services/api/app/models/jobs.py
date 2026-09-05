from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of background work for the worker to pick up — the local
    (Postgres-backed) implementation of QueueProvider on the api side.

    api only ever inserts rows here (inside the same transaction as the
    work that triggered the job, e.g. order creation); the worker is the
    only reader, via `SELECT ... FOR UPDATE SKIP LOCKED` against this
    same table (see worker/queue/local.py). available_at is the
    visibility-timeout/backoff mechanism — a job isn't receivable again
    until that time passes, mirroring SQS's own receive/delete model
    closely enough that swapping in SQSQueueProvider is a drop-in, not a
    redesign.
    """

    __tablename__ = "background_jobs"

    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
