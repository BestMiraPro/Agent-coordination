from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from uuid import UUID

from packages.core.domain.models import (
    EngineeringArtifact,
    EngineeringStage,
    EngineeringStatus,
    Job,
    JobType,
    ModelCall,
    ModelCallStatus,
)
from packages.core.engineering.orchestration import EngineeringOrchestrator
from packages.core.engineering.testing import EngineeringTestRunner
from packages.core.ports.repositories import UnitOfWork
from packages.core.structured_outputs import (
    parse_engineering_implementation,
    parse_engineering_plan,
    parse_engineering_review,
)
from packages.prompts.engineering import (
    build_engineering_implementation_request,
    build_engineering_plan_request,
    build_engineering_repair_request,
    build_engineering_review_request,
)
from packages.providers.base import ModelProvider, ModelRequest, ModelResponse

ENGINEERING_JOB_TYPES = {
    JobType.ENGINEERING_PLAN,
    JobType.ENGINEERING_IMPLEMENT,
    JobType.ENGINEERING_TEST,
    JobType.ENGINEERING_REVIEW,
    JobType.ENGINEERING_REPAIR,
}


class EngineeringJobHandler:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        orchestrator: EngineeringOrchestrator,
        provider: ModelProvider,
        model_profile_id: UUID,
        model_profile_name: str,
        test_runner: EngineeringTestRunner | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.orchestrator = orchestrator
        self.provider = provider
        self.model_profile_id = model_profile_id
        self.model_profile_name = model_profile_name
        self.test_runner = test_runner or EngineeringTestRunner()

    async def handle(self, job: Job) -> None:
        if job.job_type == JobType.ENGINEERING_PLAN:
            await self._plan(job)
        elif job.job_type == JobType.ENGINEERING_IMPLEMENT:
            await self._implement(job)
        elif job.job_type == JobType.ENGINEERING_TEST:
            await self._test(job)
        elif job.job_type == JobType.ENGINEERING_REVIEW:
            await self._review(job)
        elif job.job_type == JobType.ENGINEERING_REPAIR:
            await self._repair(job)
        else:
            raise ValueError(f"Unsupported engineering job: {job.job_type}")

    async def _plan(self, job: Job) -> None:
        run_id = UUID(str(job.payload["engineering_run_id"]))
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            existing = uow.engineering_artifacts.list_for_stage(
                run_id,
                EngineeringStage.PLAN,
                repair_cycle=0,
            )
            if existing:
                self.orchestrator.plan_completed(run_id)
                return

        request = build_engineering_plan_request(run, self.model_profile_name)
        response = await self._generate(run_id, request)
        parsed = parse_engineering_plan(response.text)
        artifact = EngineeringArtifact(
            engineering_run_id=run_id,
            stage=EngineeringStage.PLAN,
            role="planner",
            content=parsed.model_dump(),
            raw_response=response.text,
            repair_cycle=0,
        )
        with self.uow_factory() as uow:
            uow.engineering_artifacts.add(artifact)
            uow.commit()
        self.orchestrator.plan_completed(run_id)

    async def _implement(self, job: Job) -> None:
        run_id = UUID(str(job.payload["engineering_run_id"]))
        role = str(job.payload["role"])
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            existing = [
                artifact
                for artifact in uow.engineering_artifacts.list_for_stage(
                    run_id,
                    EngineeringStage.IMPLEMENTATION,
                    repair_cycle=0,
                )
                if artifact.role == role
            ]
            if existing:
                self.orchestrator.maybe_schedule_tests(run_id)
                return
            plans = uow.engineering_artifacts.list_for_stage(
                run_id,
                EngineeringStage.PLAN,
                repair_cycle=0,
            )
            if not plans:
                raise RuntimeError("Engineering plan is missing")
            plan = plans[-1].content

        request = build_engineering_implementation_request(
            run,
            plan,
            role,
            self.model_profile_name,
        )
        response = await self._generate(run_id, request)
        parsed = parse_engineering_implementation(response.text)
        artifact = EngineeringArtifact(
            engineering_run_id=run_id,
            stage=EngineeringStage.IMPLEMENTATION,
            role=role,
            content=parsed.model_dump(),
            raw_response=response.text,
            repair_cycle=0,
        )
        with self.uow_factory() as uow:
            uow.engineering_artifacts.add(artifact)
            uow.commit()
        self.orchestrator.maybe_schedule_tests(run_id)

    async def _test(self, job: Job) -> None:
        run_id = UUID(str(job.payload["engineering_run_id"]))
        repair_cycle = int(job.payload.get("repair_cycle", 0))
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            existing_checks = uow.engineering_checks.list_for_cycle(
                run_id,
                repair_cycle,
            )
            if existing_checks:
                self.orchestrator.tests_completed(run_id)
                return
            stage = (
                EngineeringStage.IMPLEMENTATION
                if repair_cycle == 0
                else EngineeringStage.REPAIR
            )
            artifacts = uow.engineering_artifacts.list_for_stage(
                run_id,
                stage,
                repair_cycle=repair_cycle,
            )
            if not artifacts:
                raise RuntimeError("No engineering artifacts available for tests")

        checks = self.test_runner.run(
            engineering_run_id=run_id,
            repair_cycle=repair_cycle,
            implementation_payloads=[artifact.content for artifact in artifacts],
        )
        with self.uow_factory() as uow:
            uow.engineering_checks.add_many(checks)
            uow.commit()
        self.orchestrator.tests_completed(run_id)

    async def _review(self, job: Job) -> None:
        run_id = UUID(str(job.payload["engineering_run_id"]))
        repair_cycle = int(job.payload.get("repair_cycle", 0))
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            existing = uow.engineering_artifacts.list_for_stage(
                run_id,
                EngineeringStage.REVIEW,
                repair_cycle=repair_cycle,
            )
            if existing:
                approved = bool(existing[-1].content.get("approve"))
                checks = uow.engineering_checks.list_for_cycle(
                    run_id,
                    repair_cycle,
                )
                self.orchestrator.review_completed(
                    run_id,
                    approved=approved and self.test_runner.all_passed(checks),
                )
                return
            stage = (
                EngineeringStage.IMPLEMENTATION
                if repair_cycle == 0
                else EngineeringStage.REPAIR
            )
            artifacts = uow.engineering_artifacts.list_for_stage(
                run_id,
                stage,
                repair_cycle=repair_cycle,
            )
            checks = uow.engineering_checks.list_for_cycle(run_id, repair_cycle)
            if not artifacts or not checks:
                raise RuntimeError("Review context is incomplete")

        checks_payload = [
            {
                "name": check.name,
                "passed": check.passed,
                "detail": check.detail,
            }
            for check in checks
        ]
        request = build_engineering_review_request(
            run,
            [artifact.content for artifact in artifacts],
            checks_payload,
            self.model_profile_name,
        )
        response = await self._generate(run_id, request)
        parsed = parse_engineering_review(response.text)
        artifact = EngineeringArtifact(
            engineering_run_id=run_id,
            stage=EngineeringStage.REVIEW,
            role="system_reviewer",
            content=parsed.model_dump(),
            raw_response=response.text,
            repair_cycle=repair_cycle,
        )
        with self.uow_factory() as uow:
            uow.engineering_artifacts.add(artifact)
            uow.commit()

        approved = parsed.approve and self.test_runner.all_passed(checks)
        self.orchestrator.review_completed(run_id, approved=approved)

    async def _repair(self, job: Job) -> None:
        run_id = UUID(str(job.payload["engineering_run_id"]))
        previous_cycle = int(job.payload.get("repair_cycle", 0))
        target_cycle = previous_cycle + 1
        with self.uow_factory() as uow:
            run = uow.engineering_runs.get(run_id)
            if run is None or run.status in {
                EngineeringStatus.COMPLETED,
                EngineeringStatus.FAILED,
            }:
                return
            existing = uow.engineering_artifacts.list_for_stage(
                run_id,
                EngineeringStage.REPAIR,
                repair_cycle=target_cycle,
            )
            if existing:
                self.orchestrator.repair_completed(run_id)
                return

            source_stage = (
                EngineeringStage.IMPLEMENTATION
                if previous_cycle == 0
                else EngineeringStage.REPAIR
            )
            artifacts = uow.engineering_artifacts.list_for_stage(
                run_id,
                source_stage,
                repair_cycle=previous_cycle,
            )
            checks = uow.engineering_checks.list_for_cycle(
                run_id,
                previous_cycle,
            )
            reviews = uow.engineering_artifacts.list_for_stage(
                run_id,
                EngineeringStage.REVIEW,
                repair_cycle=previous_cycle,
            )
            if not artifacts or not checks or not reviews:
                raise RuntimeError("Repair context is incomplete")

        request = build_engineering_repair_request(
            run,
            [artifact.content for artifact in artifacts],
            [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "detail": check.detail,
                }
                for check in checks
            ],
            reviews[-1].content,
            self.model_profile_name,
        )
        response = await self._generate(run_id, request)
        parsed = parse_engineering_implementation(response.text)
        artifact = EngineeringArtifact(
            engineering_run_id=run_id,
            stage=EngineeringStage.REPAIR,
            role="repair_engineer",
            content=parsed.model_dump(),
            raw_response=response.text,
            repair_cycle=target_cycle,
        )
        with self.uow_factory() as uow:
            uow.engineering_artifacts.add(artifact)
            uow.commit()
        self.orchestrator.repair_completed(run_id)

    async def _generate(
        self,
        engineering_run_id: UUID,
        request: ModelRequest,
    ) -> ModelResponse:
        response: ModelResponse | None = None
        try:
            response = await self.provider.generate(request)
        except Exception as exc:
            self._record_call(
                engineering_run_id,
                request,
                None,
                status=ModelCallStatus.FAILED,
                error=str(exc),
            )
            raise
        self._record_call(
            engineering_run_id,
            request,
            response,
            status=ModelCallStatus.COMPLETED,
        )
        return response

    def _record_call(
        self,
        engineering_run_id: UUID,
        request: ModelRequest,
        response: ModelResponse | None,
        *,
        status: ModelCallStatus,
        error: str | None = None,
    ) -> None:
        profile_id = self.model_profile_id
        if response is not None:
            routed = response.raw_metadata.get("routed_model_profile_id")
            if routed:
                profile_id = UUID(str(routed))

        with self.uow_factory() as uow:
            uow.model_calls.add(
                ModelCall(
                    model_profile_id=profile_id,
                    engineering_run_id=engineering_run_id,
                    task_type=request.task_type,
                    status=status,
                    latency_ms=response.latency_ms if response else None,
                    input_tokens=response.input_tokens if response else None,
                    output_tokens=response.output_tokens if response else None,
                    estimated_cost=(
                        Decimal(str(response.estimated_cost))
                        if response and response.estimated_cost is not None
                        else None
                    ),
                    request_metadata=request.metadata,
                    response_metadata=(
                        {
                            **response.raw_metadata,
                            "raw_text": response.text,
                            "provider": response.provider,
                            "model": response.model,
                        }
                        if response
                        else {}
                    ),
                    error=error,
                )
            )
            uow.model_states.observe_call(
                profile_id,
                success=status == ModelCallStatus.COMPLETED,
                latency_ms=response.latency_ms if response else None,
            )
            uow.commit()

    async def handle_terminal_failure(self, job: Job, error: Exception) -> None:
        run_id = job.payload.get("engineering_run_id")
        if run_id is not None:
            self.orchestrator.fail(UUID(str(run_id)))


class CompositeJobHandler:
    def __init__(self, research_handler, engineering_handler: EngineeringJobHandler) -> None:
        self.research_handler = research_handler
        self.engineering_handler = engineering_handler

    async def handle(self, job: Job) -> None:
        if job.job_type in ENGINEERING_JOB_TYPES:
            await self.engineering_handler.handle(job)
        else:
            await self.research_handler.handle(job)

    async def handle_terminal_failure(self, job: Job, error: Exception) -> None:
        if job.job_type in ENGINEERING_JOB_TYPES:
            await self.engineering_handler.handle_terminal_failure(job, error)
        else:
            await self.research_handler.handle_terminal_failure(job, error)
