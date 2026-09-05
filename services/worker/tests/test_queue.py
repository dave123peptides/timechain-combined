from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import create_engine, text

from worker.config import get_settings
from worker.queue.local import LocalQueueProvider

_TEST_JOB_TYPE_PREFIX = "test_queue_job"


@pytest.fixture
def engine():
    eng = create_engine(get_settings().database_url)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM background_jobs WHERE job_type LIKE :prefix"), {"prefix": f"{_TEST_JOB_TYPE_PREFIX}%"})
    eng.dispose()


@pytest.fixture
def queue(engine):
    return LocalQueueProvider(engine)


def test_enqueue_receive_delete_round_trip(queue):
    queue.enqueue(job_type=f"{_TEST_JOB_TYPE_PREFIX}_roundtrip", payload={"foo": "bar"})

    jobs = queue.receive(max_messages=10, visibility_timeout_seconds=30)
    matching = [j for j in jobs if j.job_type == f"{_TEST_JOB_TYPE_PREFIX}_roundtrip"]
    assert len(matching) == 1
    job = matching[0]
    assert job.payload == {"foo": "bar"}
    assert job.attempts == 1

    queue.delete(job.receipt_handle)

    jobs_after = queue.receive(max_messages=10, visibility_timeout_seconds=30)
    assert all(j.job_type != f"{_TEST_JOB_TYPE_PREFIX}_roundtrip" for j in jobs_after)


def test_received_job_is_invisible_until_deleted_or_timeout(queue):
    job_type = f"{_TEST_JOB_TYPE_PREFIX}_visibility"
    queue.enqueue(job_type=job_type, payload={})

    first = [j for j in queue.receive(max_messages=10, visibility_timeout_seconds=1) if j.job_type == job_type]
    assert len(first) == 1

    # Not deleted yet, and visibility timeout hasn't elapsed — must not be
    # handed out again.
    immediate = [j for j in queue.receive(max_messages=10, visibility_timeout_seconds=1) if j.job_type == job_type]
    assert immediate == []

    time.sleep(1.2)

    retried = [j for j in queue.receive(max_messages=10, visibility_timeout_seconds=1) if j.job_type == job_type]
    assert len(retried) == 1
    assert retried[0].id == first[0].id
    assert retried[0].attempts == 2  # bumped on every claim, including retries

    queue.delete(retried[0].receipt_handle)


def test_concurrent_receive_never_returns_the_same_job_twice(queue):
    job_type = f"{_TEST_JOB_TYPE_PREFIX}_concurrent"
    job_count = 20
    for i in range(job_count):
        queue.enqueue(job_type=job_type, payload={"i": i})

    received_ids: list[list] = [[], []]

    def worker(slot: int) -> None:
        for _ in range(job_count):
            jobs = queue.receive(max_messages=1, visibility_timeout_seconds=30)
            if jobs:
                received_ids[slot].append(jobs[0].id)
            else:
                break

    threads = [threading.Thread(target=worker, args=(0,)), threading.Thread(target=worker, args=(1,))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_ids = received_ids[0] + received_ids[1]
    assert len(all_ids) == job_count
    assert len(set(all_ids)) == job_count  # SKIP LOCKED: no job claimed twice

    for job_id in all_ids:
        queue.delete(str(job_id))


def test_enqueue_with_delay_is_not_receivable_until_delay_elapses(queue):
    """The mechanism submit_supplier_order's bounded retry/backoff relies
    on — see worker/jobs/submit_supplier_order.py and
    worker/alliancetek/errors.py's RETRY_DELAYS_SECONDS."""
    job_type = f"{_TEST_JOB_TYPE_PREFIX}_delayed"
    queue.enqueue(job_type=job_type, payload={}, delay_seconds=2)

    immediate = [j for j in queue.receive(max_messages=10) if j.job_type == job_type]
    assert immediate == []

    time.sleep(2.2)

    delayed = [j for j in queue.receive(max_messages=10) if j.job_type == job_type]
    assert len(delayed) == 1
    queue.delete(delayed[0].receipt_handle)


def test_enqueue_without_delay_is_immediately_receivable(queue):
    job_type = f"{_TEST_JOB_TYPE_PREFIX}_no_delay"
    queue.enqueue(job_type=job_type, payload={}, delay_seconds=0)

    immediate = [j for j in queue.receive(max_messages=10) if j.job_type == job_type]
    assert len(immediate) == 1
    queue.delete(immediate[0].receipt_handle)
