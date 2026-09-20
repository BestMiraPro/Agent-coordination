from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import Job, JobStatus, JobType
from packages.persistence.mappers import job_from_record
from packages.persistence.models import JobRecord


def retry_delay_seconds(attempt: int, *, base_seconds: int = 2, max_seconds: int = 300) -> int:
    if attempt <= 0:
        return 0
    return min(base_seconds * (2 ** (attempt - 1)), max_seconds)


class DurableJobQueue:
    def __init__(self, session_factory: sessionmaker[Session], worker_id: str) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id

    def enqueue(self, job_type: JobType, payload: dict[str, Any], idempotency_key: str, max_attempts: int = 3, available_at: datetime | None = None) -> Job:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        now = datetime.now(UTC)
        with self.session_factory() as session:
            with session.begin():
                session.execute(
                    pg_insert(JobRecord)
                    .values(
                        id=uuid4(), job_type=job_type.value, payload=payload,
                        status=JobStatus.PENDING.value, idempotency_key=idempotency_key,
                        attempt=0, max_attempts=max_attempts, available_at=available_at or now,
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                )
                record = session.execute(select(JobRecord).where(JobRecord.idempotency_key == idempotency_key)).scalar_one()
                job = job_from_record(record)
        return job

    def claim_next(self, lease_seconds: int = 120) -> Job | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = datetime.now(UTC)
        with self.session_factory() as session:
            with session.begin():
                self._requeue_expired_leases(session, now)
                record = session.execute(
                    select(JobRecord)
                    .where(
                        JobRecord.status.in_([JobStatus.PENDING.value, JobStatus.RETRY.value]),
                        JobRecord.available_at <= now,
                    )
                    .order_by(JobRecord.available_at, JobRecord.created_at, JobRecord.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                ).scalar_one_or_none()
                if record is None:
                    return None
                record.status = JobStatus.RUNNING.value
                record.attempt += 1
                record.claimed_by = self.worker_id
                record.claimed_at = now
                record.lease_expires_at = now + timedelta(seconds=lease_seconds)
                record.last_error = None
                session.flush()
                job = job_from_record(record)
        return job

    def heartbeat(self, job_id: UUID, lease_seconds: int = 120) -> bool:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = datetime.now(UTC)
        with self.session_factory() as session:
            with session.begin():
                result = session.execute(
                    update(JobRecord)
                    .where(JobRecord.id == job_id, JobRecord.status == JobStatus.RUNNING.value, JobRecord.claimed_by == self.worker_id)
                    .values(lease_expires_at=now + timedelta(seconds=lease_seconds))
                )
                return result.rowcount == 1

    def complete(self, job_id: UUID) -> bool:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            with session.begin():
                result = session.execute(
                    update(JobRecord)
                    .where(JobRecord.id == job_id, JobRecord.status == JobStatus.RUNNING.value, JobRecord.claimed_by == self.worker_id)
                    .values(status=JobStatus.COMPLETED.value, completed_at=now, claimed_at=None, lease_expires_at=None, claimed_by=None)
                )
                return result.rowcount == 1

    def fail(self, job_id: UUID, error: str, retry_delay: int | None = None) -> Job:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            with session.begin():
                record = session.execute(select(JobRecord).where(JobRecord.id == job_id).with_for_update()).scalar_one_or_none()
                if record is None:
                    raise KeyError(f"Job not found: {job_id}")
                if record.status != JobStatus.RUNNING.value:
                    raise RuntimeError(f"Job is not running: {job_id}")
                if record.claimed_by != self.worker_id:
                    raise RuntimeError(f"Job is claimed by another worker: {job_id}")
                if record.attempt >= record.max_attempts:
                    record.status = JobStatus.FAILED.value
                    record.completed_at = now
                else:
                    delay = retry_delay if retry_delay is not None else retry_delay_seconds(record.attempt)
                    if delay < 0:
                        raise ValueError("retry_delay cannot be negative")
                    record.status = JobStatus.RETRY.value
                    record.available_at = now + timedelta(seconds=delay)
                record.last_error = error
                record.claimed_at = None
                record.lease_expires_at = None
                record.claimed_by = None
                session.flush()
                job = job_from_record(record)
        return job

    def get(self, job_id: UUID) -> Job | None:
        with self.session_factory() as session:
            record = session.get(JobRecord, job_id)
            return job_from_record(record) if record else None

    def _requeue_expired_leases(self, session: Session, now: datetime) -> None:
        session.execute(
            update(JobRecord)
            .where(
                JobRecord.status == JobStatus.RUNNING.value,
                JobRecord.lease_expires_at.is_not(None),
                JobRecord.lease_expires_at < now,
                JobRecord.attempt >= JobRecord.max_attempts,
            )
            .values(
                status=JobStatus.FAILED.value, completed_at=now, claimed_at=None,
                lease_expires_at=None, claimed_by=None,
                last_error="worker lease expired after maximum attempts",
            )
        )
        session.execute(
            update(JobRecord)
            .where(
                JobRecord.status == JobStatus.RUNNING.value,
                JobRecord.lease_expires_at.is_not(None),
                JobRecord.lease_expires_at < now,
                JobRecord.attempt < JobRecord.max_attempts,
            )
            .values(
                status=JobStatus.RETRY.value, available_at=now, claimed_at=None,
                lease_expires_at=None, claimed_by=None, last_error="worker lease expired",
            )
        )
