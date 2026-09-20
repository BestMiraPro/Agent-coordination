from __future__ import annotations

import asyncio
import json
import os
from time import monotonic
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    JobType,
    Problem,
    Run,
    RunEvent,
    RunEventType,
)
from packages.persistence.database import build_engine, build_session_factory
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from services.api.app.schemas import (
    AgentResponse,
    ClaimResponse,
    EvaluationResponse,
    GenerationResponse,
    ProblemCreate,
    ProblemResponse,
    RunCreate,
    RunCreatedResponse,
    RunDetailResponse,
    SelectionResponse,
    LineageResponse,
    KnowledgeResponse,
    SubmissionResponse,
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
        "/problems",
        response_model=ProblemResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_problem(body: ProblemCreate) -> ProblemResponse:
        problem = Problem(title=body.title, prompt=body.prompt)
        with uow() as work:
            work.problems.add(problem)
            work.commit()

        return ProblemResponse(
            id=problem.id,
            title=problem.title,
            prompt=problem.prompt,
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
                knowledge = work.knowledge.list_for_generation(generation.id)

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
            problem=ProblemResponse(
                id=problem.id,
                title=problem.title,
                prompt=problem.prompt,
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
