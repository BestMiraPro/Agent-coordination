from __future__ import annotations

import asyncio
import json
import os
from statistics import pstdev
from time import monotonic
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    EngineeringRun,
    JobType,
    KnowledgeItem,
    Problem,
    Project,
    Run,
    RunEvent,
    RunEventType,
)
from packages.core.engineering.orchestration import EngineeringOrchestrator
from packages.persistence.database import build_engine, build_session_factory
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from services.api.app.schemas import (
    AgentResponse,
    CandidateStateResponse,
    ClaimResponse,
    CriticFindingResponse,
    CrossPollinationResponse,
    EngineeringArtifactResponse,
    EngineeringCheckResponse,
    EngineeringRunCreate,
    EngineeringRunDetailResponse,
    EngineeringRunSummaryResponse,
    EvaluationResponse,
    GenerationResponse,
    KnowledgeResponse,
    LineageResponse,
    ManualKnowledgeCreate,
    ModelStateResponse,
    ProblemCreate,
    ProblemResponse,
    ProjectCreate,
    ProjectResponse,
    RunCreate,
    RunCreatedResponse,
    RunDetailResponse,
    RunMetricsResponse,
    RunSummaryResponse,
    SelectionResponse,
    SubmissionResponse,
    VerificationResponse,
)


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    queue: DurableJobQueue | None = None,
) -> FastAPI:
    app = FastAPI(title="Agent Coordination API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "WEB_ORIGIN",
                "http://localhost:3000",
            ).split(",")
            if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    if session_factory is None:
        engine = build_engine()
        session_factory = build_session_factory(engine)
    if queue is None:
        queue = DurableJobQueue(session_factory, worker_id="api")

    app.state.session_factory = session_factory
    app.state.queue = queue

    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(app.state.session_factory)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/engineering-runs",
        response_model=EngineeringRunSummaryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_engineering_run(
        body: EngineeringRunCreate,
    ) -> EngineeringRunSummaryResponse:
        run = EngineeringRun(
            title=body.title,
            objective=body.objective,
            project_id=body.project_id,
            max_repairs=body.max_repairs,
        )
        with uow() as work:
            if body.project_id is not None and work.projects.get(body.project_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            work.engineering_runs.add(run)
            work.commit()

        EngineeringOrchestrator(uow, app.state.queue).start(run.id)
        with uow() as work:
            stored = work.engineering_runs.get(run.id)
            assert stored is not None
        return EngineeringRunSummaryResponse(
            id=stored.id,
            project_id=stored.project_id,
            title=stored.title,
            objective=stored.objective,
            status=stored.status,
            repair_count=stored.repair_count,
            max_repairs=stored.max_repairs,
        )

    @app.get(
        "/engineering-runs",
        response_model=list[EngineeringRunSummaryResponse],
    )
    async def list_engineering_runs() -> list[EngineeringRunSummaryResponse]:
        with uow() as work:
            runs = work.engineering_runs.list_all()
        return [
            EngineeringRunSummaryResponse(
                id=run.id,
                project_id=run.project_id,
                title=run.title,
                objective=run.objective,
                status=run.status,
                repair_count=run.repair_count,
                max_repairs=run.max_repairs,
            )
            for run in runs
        ]

    @app.get(
        "/engineering-runs/{engineering_run_id}",
        response_model=EngineeringRunDetailResponse,
    )
    async def get_engineering_run(
        engineering_run_id: UUID,
    ) -> EngineeringRunDetailResponse:
        with uow() as work:
            run = work.engineering_runs.get(engineering_run_id)
            if run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Engineering run not found",
                )
            artifacts = work.engineering_artifacts.list_for_run(engineering_run_id)
            checks = work.engineering_checks.list_for_run(engineering_run_id)
        return EngineeringRunDetailResponse(
            id=run.id,
            project_id=run.project_id,
            title=run.title,
            objective=run.objective,
            status=run.status,
            repair_count=run.repair_count,
            max_repairs=run.max_repairs,
            artifacts=[
                EngineeringArtifactResponse(
                    id=artifact.id,
                    stage=artifact.stage,
                    role=artifact.role,
                    content=artifact.content,
                    repair_cycle=artifact.repair_cycle,
                )
                for artifact in artifacts
            ],
            checks=[
                EngineeringCheckResponse(
                    id=check.id,
                    name=check.name,
                    passed=check.passed,
                    detail=check.detail,
                    repair_cycle=check.repair_cycle,
                )
                for check in checks
            ],
        )

    @app.post(
        "/projects",
        response_model=ProjectResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_project(body: ProjectCreate) -> ProjectResponse:
        project = Project(name=body.name, description=body.description)
        with uow() as work:
            work.projects.add(project)
            work.commit()
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
        )

    @app.get("/projects", response_model=list[ProjectResponse])
    async def list_projects() -> list[ProjectResponse]:
        with uow() as work:
            projects = work.projects.list_all()
        return [
            ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
            )
            for project in projects
        ]

    @app.post(
        "/problems",
        response_model=ProblemResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_problem(body: ProblemCreate) -> ProblemResponse:
        problem = Problem(
            title=body.title,
            prompt=body.prompt,
            project_id=body.project_id,
        )
        with uow() as work:
            if body.project_id is not None and work.projects.get(body.project_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            work.problems.add(problem)
            work.commit()

        return ProblemResponse(
            id=problem.id,
            title=problem.title,
            prompt=problem.prompt,
            project_id=problem.project_id,
        )

    @app.post(
        "/runs",
        response_model=RunCreatedResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_run(body: RunCreate) -> RunCreatedResponse:
        run = Run(
            problem_id=body.problem_id,
            max_generations=body.max_generations,
            population_size=body.population_size,
            survivor_count=body.survivor_count,
            fresh_agent_count=body.fresh_agent_count,
            redundancy_threshold=body.redundancy_threshold,
            critic_count=body.critic_count,
            verification_enabled=body.verification_enabled,
        )

        with uow() as work:
            problem = work.problems.get(body.problem_id)
            if problem is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Problem not found",
                )

            work.runs.add(run)
            work.events.append(
                RunEvent(
                    run_id=run.id,
                    event_type=RunEventType.RUN_CREATED.value,
                    payload={
                        "problem_id": str(body.problem_id),
                        "max_generations": run.max_generations,
                        "population_size": run.population_size,
                        "survivor_count": run.survivor_count,
                        "fresh_agent_count": run.fresh_agent_count,
                        "redundancy_threshold": run.redundancy_threshold,
                        "critic_count": run.critic_count,
                        "verification_enabled": run.verification_enabled,
                    },
                )
            )
            work.commit()

        app.state.queue.enqueue(
            JobType.CREATE_GENERATION,
            {"run_id": str(run.id)},
            idempotency_key=f"run:{run.id}:create-generation",
        )

        return RunCreatedResponse(
            id=run.id,
            problem_id=run.problem_id,
            status=run.status,
            max_generations=run.max_generations,
            population_size=run.population_size,
            survivor_count=run.survivor_count,
            fresh_agent_count=run.fresh_agent_count,
            redundancy_threshold=run.redundancy_threshold,
            critic_count=run.critic_count,
            verification_enabled=run.verification_enabled,
        )

    @app.get("/runs", response_model=list[RunSummaryResponse])
    async def list_runs() -> list[RunSummaryResponse]:
        with uow() as work:
            runs = work.runs.list_all()
        return [
            RunSummaryResponse(
                id=run.id,
                problem_id=run.problem_id,
                status=run.status,
                max_generations=run.max_generations,
                population_size=run.population_size,
                survivor_count=run.survivor_count,
                fresh_agent_count=run.fresh_agent_count,
                critic_count=run.critic_count,
                verification_enabled=run.verification_enabled,
            )
            for run in runs
        ]

    @app.get("/model-states", response_model=list[ModelStateResponse])
    async def get_model_states() -> list[ModelStateResponse]:
        with uow() as work:
            states = work.model_states.list_all()
        return [
            ModelStateResponse(
                id=state.id,
                model_profile_id=state.model_profile_id,
                quality_by_task=state.quality_by_task,
                marginal_cash_cost=state.marginal_cash_cost,
                credit_cost=state.credit_cost,
                latency_ms=state.latency_ms,
                scarcity=state.scarcity,
                failure_rate=state.failure_rate,
                rate_limit_pressure=state.rate_limit_pressure,
                available_concurrency=state.available_concurrency,
                enabled=state.enabled,
            )
            for state in states
        ]

    @app.get("/runs/{run_id}/metrics", response_model=RunMetricsResponse)
    async def get_run_metrics(run_id: UUID) -> RunMetricsResponse:
        with uow() as work:
            run = work.runs.get(run_id)
            if run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Run not found",
                )
            generations = work.generations.list_for_run(run_id)
            calls = work.model_calls.list_for_run(run_id)
            knowledge = work.knowledge.list_for_run(run_id)
            verification_count = 0
            verified_candidates = 0
            niches: set[str] = set()
            correctness_groups: dict[UUID, list[float]] = {}
            for generation in generations:
                verification_count += len(
                    work.verifications.list_for_generation(generation.id)
                )
                for state in work.candidate_states.list_for_generation(generation.id):
                    if state.status.value == "VERIFIED":
                        verified_candidates += 1
                for agent in work.agents.list_for_generation(generation.id):
                    if agent.role.startswith("researcher:"):
                        niches.add(agent.niche.value)
                for evaluation in work.evaluations.list_for_generation(generation.id):
                    correctness_groups.setdefault(
                        evaluation.submission_id,
                        [],
                    ).append(evaluation.correctness)

        disagreements = [
            pstdev(scores)
            for scores in correctness_groups.values()
            if len(scores) > 1
        ]
        return RunMetricsResponse(
            model_calls=len(calls),
            input_tokens=sum(call.input_tokens or 0 for call in calls),
            output_tokens=sum(call.output_tokens or 0 for call in calls),
            estimated_cost=float(sum(call.estimated_cost or 0 for call in calls)),
            generations=len(generations),
            knowledge_items=len(knowledge),
            verifications=verification_count,
            verified_candidates=verified_candidates,
            active_niches=len(niches),
            judge_disagreement=(
                sum(disagreements) / len(disagreements)
                if disagreements
                else 0.0
            ),
        )

    @app.post(
        "/runs/{run_id}/knowledge",
        response_model=KnowledgeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def inject_knowledge(
        run_id: UUID,
        body: ManualKnowledgeCreate,
    ) -> KnowledgeResponse:
        with uow() as work:
            run = work.runs.get(run_id)
            if run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Run not found",
                )
            generations = work.generations.list_for_run(run_id)
            if not generations:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Run has no generation yet",
                )
            generation = generations[-1]
            item = KnowledgeItem(
                run_id=run_id,
                generation_id=generation.id,
                submission_id=None,
                kind=body.kind,
                content=body.content,
                confidence=body.confidence,
                provenance={"source": "manual_control_room"},
            )
            work.knowledge.add_many([item])
            work.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.KNOWLEDGE_CREATED.value,
                    payload={
                        "knowledge_id": str(item.id),
                        "generation_id": str(generation.id),
                        "kind": item.kind.value,
                        "source": "manual_control_room",
                    },
                )
            )
            work.commit()
        return KnowledgeResponse(
            id=item.id,
            generation_id=item.generation_id,
            submission_id=item.submission_id,
            kind=item.kind,
            content=item.content,
            status=item.status,
            confidence=item.confidence,
            provenance=item.provenance,
        )

    @app.get("/runs/{run_id}", response_model=RunDetailResponse)
    async def get_run(run_id: UUID) -> RunDetailResponse:
        with uow() as work:
            run = work.runs.get(run_id)
            if run is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Run not found",
                )

            problem = work.problems.get(run.problem_id)
            if problem is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Run problem is missing",
                )

            generations: list[GenerationResponse] = []
            for generation in work.generations.list_for_run(run_id):
                agents = work.agents.list_for_generation(generation.id)
                submissions = work.submissions.list_for_generation(generation.id)
                evaluations = work.evaluations.list_for_generation(generation.id)
                selections = work.selections.list_for_generation(generation.id)
                lineages = work.lineages.list_for_generation(generation.id)
                cross_pollination = work.cross_pollination.list_for_generation(generation.id)
                knowledge = work.knowledge.list_for_generation(generation.id)
                candidate_states = work.candidate_states.list_for_generation(generation.id)
                critic_findings = work.critic_findings.list_for_generation(generation.id)
                verifications = work.verifications.list_for_generation(generation.id)

                generations.append(
                    GenerationResponse(
                        id=generation.id,
                        index=generation.index,
                        agents=[
                            AgentResponse(
                                id=agent.id,
                                role=agent.role,
                                status=agent.status,
                                niche=agent.niche,
                                origin=agent.origin,
                            )
                            for agent in agents
                        ],
                        submissions=[
                            SubmissionResponse(
                                id=submission.id,
                                agent_id=submission.agent_id,
                                summary=submission.summary,
                                approach=submission.approach,
                                claims=[
                                    ClaimResponse(
                                        statement=claim.statement,
                                        confidence=claim.confidence,
                                        support=claim.support,
                                    )
                                    for claim in submission.claims
                                ],
                                evidence=submission.evidence,
                                discoveries=submission.discoveries,
                                failed_attempts=submission.failed_attempts,
                                open_questions=submission.open_questions,
                                final_answer=submission.final_answer,
                                raw_response=submission.raw_response,
                            )
                            for submission in submissions
                        ],
                        evaluations=[
                            EvaluationResponse(
                                id=evaluation.id,
                                submission_id=evaluation.submission_id,
                                judge_agent_id=evaluation.judge_agent_id,
                                correctness=evaluation.correctness,
                                rigor=evaluation.rigor,
                                novelty=evaluation.novelty,
                                research_progress=evaluation.research_progress,
                                verifiability=evaluation.verifiability,
                                fatal_error=evaluation.fatal_error,
                                judge_confidence=evaluation.judge_confidence,
                                critique=evaluation.critique,
                            )
                            for evaluation in evaluations
                        ],
                        selections=[
                            SelectionResponse(
                                id=decision.id,
                                submission_id=decision.submission_id,
                                selected=decision.selected,
                                rank=decision.rank,
                                score_vector=decision.score_vector,
                                reason=decision.reason,
                                selection_kind=decision.selection_kind,
                                novelty_score=decision.novelty_score,
                                redundant_with_submission_id=(
                                    decision.redundant_with_submission_id
                                ),
                            )
                            for decision in selections
                        ],
                        lineages=[
                            LineageResponse(
                                id=lineage.id,
                                child_agent_id=lineage.child_agent_id,
                                parent_submission_id=lineage.parent_submission_id,
                                mutation_type=lineage.mutation_type,
                            )
                            for lineage in lineages
                        ],
                        cross_pollination=[
                            CrossPollinationResponse(
                                id=packet.id,
                                target_agent_id=packet.target_agent_id,
                                source_submission_id=packet.source_submission_id,
                                kind=packet.kind,
                                payload=packet.payload,
                            )
                            for packet in cross_pollination
                        ],
                        knowledge=[
                            KnowledgeResponse(
                                id=item.id,
                                generation_id=item.generation_id,
                                submission_id=item.submission_id,
                                kind=item.kind,
                                content=item.content,
                                status=item.status,
                                confidence=item.confidence,
                                provenance=item.provenance,
                            )
                            for item in knowledge
                        ],
                        candidate_states=[
                            CandidateStateResponse(
                                id=state.id,
                                submission_id=state.submission_id,
                                status=state.status,
                            )
                            for state in candidate_states
                        ],
                        critic_findings=[
                            CriticFindingResponse(
                                id=finding.id,
                                critic_agent_id=finding.critic_agent_id,
                                submission_id=finding.submission_id,
                                fatal_error=finding.fatal_error,
                                confidence=finding.confidence,
                                critique=finding.critique,
                                counterexample=finding.counterexample,
                            )
                            for finding in critic_findings
                        ],
                        verifications=[
                            VerificationResponse(
                                id=result.id,
                                submission_id=result.submission_id,
                                kind=result.kind,
                                status=result.status,
                                detail=result.detail,
                                metadata=result.metadata,
                            )
                            for result in verifications
                        ],
                    )
                )

        return RunDetailResponse(
            id=run.id,
            status=run.status,
            max_generations=run.max_generations,
            population_size=run.population_size,
            survivor_count=run.survivor_count,
            fresh_agent_count=run.fresh_agent_count,
            redundancy_threshold=run.redundancy_threshold,
            critic_count=run.critic_count,
            verification_enabled=run.verification_enabled,
            problem=ProblemResponse(
                id=problem.id,
                title=problem.title,
                prompt=problem.prompt,
                project_id=problem.project_id,
            ),
            generations=generations,
        )

    @app.get("/runs/{run_id}/events")
    async def stream_run_events(
        run_id: UUID,
        request: Request,
        after_id: UUID | None = Query(default=None),
        follow: bool = Query(default=True),
        poll_interval: float = Query(default=0.5, ge=0.05, le=10.0),
    ) -> StreamingResponse:
        with uow() as work:
            if work.runs.get(run_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Run not found",
                )

        last_event_id = request.headers.get("last-event-id")
        if after_id is None and last_event_id:
            try:
                after_id = UUID(last_event_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Last-Event-ID",
                ) from exc

        async def event_source():
            cursor = after_id
            last_keepalive = monotonic()

            while True:
                if await request.is_disconnected():
                    break

                with uow() as work:
                    events = work.events.list_for_run(run_id, after_id=cursor)

                for event in events:
                    data = {
                        "id": str(event.id),
                        "type": event.event_type,
                        "payload": event.payload,
                        "created_at": (
                            event.created_at.isoformat()
                            if event.created_at is not None
                            else None
                        ),
                    }
                    yield (
                        f"id: {event.id}\n"
                        f"event: {event.event_type}\n"
                        f"data: {json.dumps(data, separators=(',', ':'), default=str)}\n\n"
                    )
                    cursor = event.id
                    last_keepalive = monotonic()

                if not follow:
                    break

                now = monotonic()
                if not events and now - last_keepalive >= 15.0:
                    yield ": keepalive\n\n"
                    last_keepalive = now

                if not events:
                    await asyncio.sleep(poll_interval)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
