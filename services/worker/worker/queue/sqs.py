from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import boto3

from worker.queue.provider import Job

logger = logging.getLogger("timechain.worker.queue.sqs")

# The only place boto3 is imported anywhere in this codebase — every other
# module depends on QueueProvider, never on AWS directly (see provider.py).

# SQS's send_message hard-caps DelaySeconds at 15 minutes. Our longest
# backoff tier (30 minutes — see worker/alliancetek/errors.py) exceeds that;
# there is no larger native delay on a single send_message call, so a
# request for more than this is capped and logged rather than silently
# truncated. A real delay-queue mechanism (e.g. a DynamoDB timer table) is
# a follow-up, not built here — same honest-placeholder posture as the rest
# of this class.
_MAX_SQS_DELAY_SECONDS = 900


class SQSQueueProvider:
    """Production QueueProvider, backed by a real AWS SQS queue.

    Structurally complete — real send_message/receive_message/
    delete_message calls, matching QueueProvider's contract exactly — but
    not yet exercised against a real SQS queue (no queue has been
    provisioned yet). Same honest-placeholder posture as
    Payment.provider="not_configured": a real implementation, not a
    fabricated one, just unverified end-to-end until a queue exists to
    point it at.
    """

    def __init__(self, *, queue_url: str, region: str) -> None:
        self._queue_url = queue_url
        self._client = boto3.client("sqs", region_name=region)

    def enqueue(self, *, job_type: str, payload: dict[str, Any], delay_seconds: int = 0) -> None:
        if delay_seconds > _MAX_SQS_DELAY_SECONDS:
            logger.warning(
                "sqs: requested delay_seconds=%s exceeds SQS's %ss max; capping (job_type=%s)",
                delay_seconds,
                _MAX_SQS_DELAY_SECONDS,
                job_type,
            )
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps({"job_type": job_type, "payload": payload}),
            DelaySeconds=min(delay_seconds, _MAX_SQS_DELAY_SECONDS),
        )

    def receive(self, *, max_messages: int = 10, visibility_timeout_seconds: int = 60) -> list[Job]:
        # SQS caps a single receive_message call at 10 messages regardless
        # of what's requested.
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            VisibilityTimeout=visibility_timeout_seconds,
            WaitTimeSeconds=10,
            AttributeNames=["ApproximateReceiveCount"],
        )

        jobs: list[Job] = []
        for message in response.get("Messages", []):
            body = json.loads(message["Body"])
            attributes = message.get("Attributes", {})
            jobs.append(
                Job(
                    id=uuid.UUID(message["MessageId"]),
                    job_type=body["job_type"],
                    payload=body["payload"],
                    attempts=int(attributes.get("ApproximateReceiveCount", 1)),
                    receipt_handle=message["ReceiptHandle"],
                )
            )
        return jobs

    def delete(self, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
