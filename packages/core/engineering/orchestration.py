from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from packages.core.domain.models import (
    EngineeringStage,
    EngineeringStatus,
    JobType,
)
from packages.core.ports.repositories import JobQueue, UnitOfWork

IMPLEMENTER_ROLES = ("primary", "test_specialist")


class EngineeringOrchestrator:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        queue: JobQueue,
    ) -> None:
        self.uow_factory = uow_factory
        self.queue = queue

    def start(self, engineering_run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status == EngineeringStatus.CREATED:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.PLANNING,
                )
                uow.commit()
            elif run.status != EngineeringStatus.PLANNING:
                return

        self.queue.enqueue(
            JobType.ENGINEERING_PLAN,
            {"engineering_run_id": str(engineering_run_id)},
            idempotency_key=f"engineering:{engineering_run_id}:plan",
        )

    def plan_completed(self, engineering_run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status == EngineeringStatus.PLANNING:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.IMPLEMENTING,
                )
                uow.commit()
            elif run.status != EngineeringStatus.IMPLEMENTING:
                return

        for role in IMPLEMENTER_ROLES:
            self.queue.enqueue(
                JobType.ENGINEERING_IMPLEMENT,
                {
                    "engineering_run_id": str(engineering_run_id),
                    "role": role,
                },
                idempotency_key=f"engineering:{engineering_run_id}:implement:{role}",
            )

    def maybe_schedule_tests(self, engineering_run_id: UUID) -> bool:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status != EngineeringStatus.IMPLEMENTING:
                return run.status in {
                    EngineeringStatus.TESTING,
                    EngineeringStatus.REVIEWING,
                    EngineeringStatus.REPAIRING,
                    EngineeringStatus.COMPLETED,
                }

            artifacts = uow.engineering_artifacts.list_for_stage(
                engineering_run_id,
                EngineeringStage.IMPLEMENTATION,
                repair_cycle=0,
            )
            roles = {artifact.role for artifact in artifacts}
            if not set(IMPLEMENTER_ROLES).issubset(roles):
                return False

            uow.engineering_runs.update_status(
                engineering_run_id,
                EngineeringStatus.TESTING,
            )
            uow.commit()

        self._enqueue_test(engineering_run_id, repair_cycle=0)
        return True

    def tests_completed(self, engineering_run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status == EngineeringStatus.TESTING:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.REVIEWING,
                )
                uow.commit()
            elif run.status != EngineeringStatus.REVIEWING:
                return
            repair_cycle = run.repair_count

        self.queue.enqueue(
            JobType.ENGINEERING_REVIEW,
            {
                "engineering_run_id": str(engineering_run_id),
                "repair_cycle": repair_cycle,
            },
            idempotency_key=(
                f"engineering:{engineering_run_id}:review:{repair_cycle}"
            ),
        )

    def review_completed(
        self,
        engineering_run_id: UUID,
        *,
        approved: bool,
    ) -> None:
        enqueue_repair = False
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status != EngineeringStatus.REVIEWING:
                return

            if approved:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.COMPLETED,
                )
            elif run.repair_count < run.max_repairs:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.REPAIRING,
                )
                enqueue_repair = True
            else:
                uow.engineering_runs.update_status(
                    engineering_run_id,
                    EngineeringStatus.FAILED,
                )
            uow.commit()

        if enqueue_repair:
            self.queue.enqueue(
                JobType.ENGINEERING_REPAIR,
                {
                    "engineering_run_id": str(engineering_run_id),
                    "repair_cycle": run.repair_count,
                },
                idempotency_key=(
                    f"engineering:{engineering_run_id}:repair:{run.repair_count + 1}"
                ),
            )

    def repair_completed(self, engineering_run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None:
                raise KeyError(f"Engineering run not found: {engineering_run_id}")
            if run.status != EngineeringStatus.REPAIRING:
                return
            run = uow.engineering_runs.increment_repair(engineering_run_id)
            uow.engineering_runs.update_status(
                engineering_run_id,
                EngineeringStatus.TESTING,
            )
            uow.commit()
            repair_cycle = run.repair_count

        self._enqueue_test(engineering_run_id, repair_cycle=repair_cycle)

    def fail(self, engineering_run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(engineering_run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            uow.engineering_runs.update_status(
                engineering_run_id,
                EngineeringStatus.FAILED,
            )
            uow.commit()

    def _enqueue_test(self, engineering_run_id: UUID, *, repair_cycle: int) -> None:
        self.queue.enqueue(
            JobType.ENGINEERING_TEST,
            {
                "engineering_run_id": str(engineering_run_id),
                "repair_cycle": repair_cycle,
            },
            idempotency_key=(
                f"engineering:{engineering_run_id}:test:{repair_cycle}"
            ),
        )
