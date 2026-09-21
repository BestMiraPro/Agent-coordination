from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from packages.core.domain.models import (
    AgentStatus,
    ClaimDraft,
    CriticFinding,
    Evaluation,
    Generation,
    Job,
    JobType,
    ModelCall,
    ModelCallStatus,
    RunEvent,
    RunEventType,
    Submission,
)
from packages.core.orchestration.baseline import blind_submissions
from packages.core.ports.repositories import UnitOfWork
from packages.core.research.memory import build_memory_packet, extract_knowledge
from packages.core.structured_outputs import (
    parse_critic_output,
    parse_judge_output,
    parse_researcher_output,
)
from packages.prompts.baseline import (
    build_critic_request,
    build_judge_request,
    build_research_request,
)
from packages.providers.base import ModelProvider, ModelRequest, ModelResponse


class RunOrchestrator(Protocol):
    def start_run(self, run_id: UUID) -> Generation: ...
    def maybe_schedule_judging(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> bool: ...
    def start_judging(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> list: ...
    def maybe_schedule_finalize(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> bool: ...
    def finalize_run(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> None: ...
    def fail_run(
        self,
        run_id: UUID,
        reason: str,
        agent_id: UUID | None = None,
    ) -> None: ...


class BaselineJobHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        orchestrator: RunOrchestrator,
        provider: ModelProvider,
        model_profile_id: UUID,
        model_profile_name: str,
    ) -> None:
        self.uow_factory = uow_factory
        self.orchestrator = orchestrator
        self.provider = provider
        self.model_profile_id = model_profile_id
        self.model_profile_name = model_profile_name

    async def handle(self, job: Job) -> None:
        if job.job_type == JobType.CREATE_GENERATION:
            self.orchestrator.start_run(UUID(str(job.payload["run_id"])))
            return
        if job.job_type == JobType.RUN_RESEARCH_AGENT:
            await self._run_research_agent(job)
            return
        if job.job_type == JobType.START_JUDGING:
            self.orchestrator.start_judging(
                UUID(str(job.payload["run_id"])),
                UUID(str(job.payload["generation_id"]))
                if job.payload.get("generation_id")
                else None,
            )
            return
        if job.job_type == JobType.RUN_JUDGE:
            await self._run_judge(job)
            return
        if job.job_type == JobType.RUN_CRITIC:
            await self._run_critic(job)
            return
        if job.job_type == JobType.FINALIZE_RUN:
            self.orchestrator.finalize_run(
                UUID(str(job.payload["run_id"])),
                UUID(str(job.payload["generation_id"]))
                if job.payload.get("generation_id")
                else None,
            )
            return
        raise ValueError(f"Unsupported job type: {job.job_type}")

    async def _run_research_agent(self, job: Job) -> None:
        agent_id = UUID(str(job.payload["agent_id"]))
        run_id = UUID(str(job.payload["run_id"]))

        with self.uow_factory() as uow:
            agent = uow.agents.get(agent_id)
            if agent is None:
                raise KeyError(f"Agent not found: {agent_id}")
            generation = uow.generations.get(agent.generation_id)
            if generation is None:
                raise RuntimeError("Agent generation is missing")

            existing = uow.submissions.get_for_agent(agent_id)
            if existing is not None:
                if agent.status != AgentStatus.COMPLETED:
                    uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
                    uow.commit()
                self.orchestrator.maybe_schedule_judging(run_id, generation.id)
                return

            run = uow.runs.get(generation.run_id)
            if run is None:
                raise RuntimeError("Agent run is missing")
            if run.status.value in {"FAILED", "COMPLETED"}:
                return
            problem = uow.problems.get(run.problem_id)
            if problem is None:
                raise RuntimeError("Run problem is missing")

            lineage = uow.lineages.get_for_child(agent_id)
            parent_submission = (
                uow.submissions.get(lineage.parent_submission_id)
                if lineage is not None
                else None
            )
            memory_context: list[dict[str, object]] = []
            if agent.origin.value != "FRESH" and generation.index > 0:
                previous_generation_ids = {
                    item.id
                    for item in uow.generations.list_for_run(run_id)
                    if item.index < generation.index
                }
                memory_context = build_memory_packet(
                    [
                        item
                        for item in uow.knowledge.list_for_run(run_id)
                        if item.generation_id in previous_generation_ids
                    ]
                )
            if lineage is not None and parent_submission is None:
                raise RuntimeError("Lineage parent submission is missing")
            cross_pollination = [
                {
                    "kind": packet.kind.value,
                    "source_submission_id": str(packet.source_submission_id),
                    "payload": packet.payload,
                }
                for packet in uow.cross_pollination.list_for_agent(agent_id)
            ]

            uow.agents.update_status(agent_id, AgentStatus.RUNNING)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.AGENT_STARTED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "role": agent.role,
                        "attempt": job.attempt,
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        request = build_research_request(
            problem,
            self.model_profile_name,
            niche=agent.niche,
            origin=agent.origin,
            parent_submission=parent_submission,
            mutation_type=lineage.mutation_type if lineage is not None else None,
            memory_context=memory_context,
            cross_pollination=cross_pollination,
        )
        response: ModelResponse | None = None
        try:
            response = await self.provider.generate(request)
            parsed = parse_researcher_output(response.text)
        except Exception as exc:
            self._record_failed_call(run_id, agent_id, request, response, exc)
            raise

        submission = Submission(
            agent_id=agent_id,
            summary=parsed.summary,
            approach=parsed.approach,
            claims=[
                ClaimDraft(
                    statement=claim.statement,
                    confidence=claim.confidence,
                    support=claim.support,
                )
                for claim in parsed.claims
            ],
            evidence=parsed.evidence,
            discoveries=parsed.discoveries,
            failed_attempts=parsed.failed_attempts,
            open_questions=parsed.open_questions,
            final_answer=parsed.final_answer,
            raw_response=response.text,
        )

        with self.uow_factory() as uow:
            if uow.submissions.get_for_agent(agent_id) is None:
                stored_submission = uow.submissions.add(submission)
                knowledge_items = extract_knowledge(
                    run_id=run_id,
                    generation_id=generation.id,
                    submission=stored_submission,
                )
                if knowledge_items:
                    uow.knowledge.add_many(knowledge_items)
                    for item in knowledge_items:
                        uow.events.append(
                            RunEvent(
                                run_id=run_id,
                                event_type=RunEventType.KNOWLEDGE_CREATED.value,
                                payload={
                                    "knowledge_id": str(item.id),
                                    "generation_id": str(generation.id),
                                    "submission_id": str(stored_submission.id),
                                    "kind": item.kind.value,
                                },
                            )
                        )
            self._add_model_call(uow, run_id, agent_id, request, response)
            uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.AGENT_COMPLETED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "role": agent.role,
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        self.orchestrator.maybe_schedule_judging(run_id, generation.id)

    async def _run_judge(self, job: Job) -> None:
        agent_id = UUID(str(job.payload["agent_id"]))
        run_id = UUID(str(job.payload["run_id"]))

        with self.uow_factory() as uow:
            judge = uow.agents.get(agent_id)
            if judge is None:
                raise KeyError(f"Judge not found: {agent_id}")
            generation = uow.generations.get(judge.generation_id)
            if generation is None:
                raise RuntimeError("Judge generation is missing")
            run = uow.runs.get(generation.run_id)
            if run is None:
                raise RuntimeError("Judge run is missing")
            if run.status.value in {"FAILED", "COMPLETED"}:
                return
            problem = uow.problems.get(run.problem_id)
            if problem is None:
                raise RuntimeError("Run problem is missing")
            submissions = uow.submissions.list_for_generation(generation.id)
            existing_evaluations = [
                evaluation
                for evaluation in uow.evaluations.list_for_generation(generation.id)
                if evaluation.judge_agent_id == agent_id
            ]
            if len(existing_evaluations) == len(submissions) and submissions:
                if judge.status != AgentStatus.COMPLETED:
                    uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
                    uow.commit()
                self.orchestrator.maybe_schedule_finalize(run_id, generation.id)
                return

            uow.agents.update_status(agent_id, AgentStatus.RUNNING)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.AGENT_STARTED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "role": judge.role,
                        "attempt": job.attempt,
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        blinded = blind_submissions(submissions, agent_id)
        request = build_judge_request(problem, blinded, self.model_profile_name)
        expected = {item.candidate_id for item in blinded}
        response: ModelResponse | None = None
        try:
            response = await self.provider.generate(request)
            parsed = parse_judge_output(response.text, expected)
        except Exception as exc:
            self._record_failed_call(run_id, agent_id, request, response, exc)
            raise

        submission_ids = {
            item.candidate_id: item.submission.id
            for item in blinded
        }

        with self.uow_factory() as uow:
            existing = {
                evaluation.submission_id
                for evaluation in uow.evaluations.list_for_generation(generation.id)
                if evaluation.judge_agent_id == agent_id
            }
            for result in parsed.evaluations:
                submission_id = submission_ids[result.candidate_id]
                if submission_id in existing:
                    continue
                evaluation = Evaluation(
                    submission_id=submission_id,
                    judge_agent_id=agent_id,
                    correctness=result.correctness,
                    rigor=result.rigor,
                    novelty=result.novelty,
                    research_progress=result.research_progress,
                    verifiability=result.verifiability,
                    fatal_error=result.fatal_error,
                    judge_confidence=result.judge_confidence,
                    critique=result.critique,
                )
                uow.evaluations.add(evaluation)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.EVALUATION_COMPLETED.value,
                        payload={
                            "evaluation_id": str(evaluation.id),
                            "submission_id": str(submission_id),
                            "judge_agent_id": str(agent_id),
                            "generation_id": str(generation.id),
                        },
                    )
                )

            self._add_model_call(uow, run_id, agent_id, request, response)
            uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.AGENT_COMPLETED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "role": judge.role,
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        self.orchestrator.maybe_schedule_finalize(run_id, generation.id)

    async def _run_critic(self, job: Job) -> None:
        agent_id = UUID(str(job.payload["agent_id"]))
        run_id = UUID(str(job.payload["run_id"]))
        submission_id = UUID(str(job.payload["submission_id"]))

        with self.uow_factory() as uow:
            critic = uow.agents.get(agent_id)
            if critic is None:
                raise KeyError(f"Critic not found: {agent_id}")
            generation = uow.generations.get(critic.generation_id)
            if generation is None:
                raise RuntimeError("Critic generation is missing")
            run = uow.runs.get(generation.run_id)
            if run is None or run.status.value in {"FAILED", "COMPLETED"}:
                return
            problem = uow.problems.get(run.problem_id)
            submission = uow.submissions.get(submission_id)
            if problem is None or submission is None:
                raise RuntimeError("Critic context is missing")

            existing = uow.critic_findings.get_for_agent_submission(
                agent_id,
                submission_id,
            )
            if existing is not None:
                if critic.status != AgentStatus.COMPLETED:
                    uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
                    uow.commit()
                self.orchestrator.maybe_schedule_finalize(run_id, generation.id)
                return

            uow.agents.update_status(agent_id, AgentStatus.RUNNING)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.CRITIC_STARTED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "submission_id": str(submission_id),
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        request = build_critic_request(
            problem,
            submission,
            self.model_profile_name,
        )
        response: ModelResponse | None = None
        try:
            response = await self.provider.generate(request)
            parsed = parse_critic_output(response.text)
        except Exception as exc:
            self._record_failed_call(run_id, agent_id, request, response, exc)
            raise

        finding = CriticFinding(
            generation_id=generation.id,
            critic_agent_id=agent_id,
            submission_id=submission_id,
            fatal_error=parsed.fatal_error,
            confidence=parsed.confidence,
            critique=parsed.critique,
            counterexample=parsed.counterexample,
        )

        with self.uow_factory() as uow:
            if (
                uow.critic_findings.get_for_agent_submission(
                    agent_id,
                    submission_id,
                )
                is None
            ):
                uow.critic_findings.add(finding)
            self._add_model_call(uow, run_id, agent_id, request, response)
            uow.agents.update_status(agent_id, AgentStatus.COMPLETED)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.CRITIC_COMPLETED.value,
                    payload={
                        "agent_id": str(agent_id),
                        "submission_id": str(submission_id),
                        "fatal_error": finding.fatal_error,
                        "confidence": finding.confidence,
                        "generation_id": str(generation.id),
                    },
                )
            )
            uow.commit()

        self.orchestrator.maybe_schedule_finalize(run_id, generation.id)

    def _record_failed_call(
        self,
        run_id: UUID,
        agent_id: UUID,
        request: ModelRequest,
        response: ModelResponse | None,
        error: Exception,
    ) -> None:
        with self.uow_factory() as uow:
            self._add_model_call(
                uow,
                run_id,
                agent_id,
                request,
                response,
                status=ModelCallStatus.FAILED,
                error=str(error),
            )
            uow.commit()

    def _add_model_call(
        self,
        uow: UnitOfWork,
        run_id: UUID,
        agent_id: UUID,
        request: ModelRequest,
        response: ModelResponse | None,
        status: ModelCallStatus = ModelCallStatus.COMPLETED,
        error: str | None = None,
    ) -> None:
        response_metadata = {}
        if response is not None:
            response_metadata = {
                **response.raw_metadata,
                "raw_text": response.text,
                "provider": response.provider,
                "model": response.model,
            }
        routed_profile_id = self.model_profile_id
        if response is not None:
            raw_profile_id = response.raw_metadata.get("routed_model_profile_id")
            if raw_profile_id:
                routed_profile_id = UUID(str(raw_profile_id))

        uow.model_calls.add(
            ModelCall(
                model_profile_id=routed_profile_id,
                run_id=run_id,
                agent_id=agent_id,
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
                retry_count=response.retry_count if response else 0,
                request_metadata=request.metadata,
                response_metadata=response_metadata,
                error=error,
            )
        )
        uow.model_states.observe_call(
            routed_profile_id,
            success=status == ModelCallStatus.COMPLETED,
            latency_ms=response.latency_ms if response else None,
        )

    async def handle_terminal_failure(self, job: Job, error: Exception) -> None:
        run_id_raw = job.payload.get("run_id")
        if run_id_raw is None:
            return
        agent_id_raw = job.payload.get("agent_id")
        self.orchestrator.fail_run(
            UUID(str(run_id_raw)),
            reason=f"{job.job_type.value} exhausted retries: {error}",
            agent_id=UUID(str(agent_id_raw)) if agent_id_raw is not None else None,
        )
