from __future__ import annotations

from collections.abc import Iterable
from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    Agent,
    AgentStatus,
    Evaluation,
    Generation,
    KnowledgeItem,
    LineageLink,
    ModelCall,
    ModelProfile,
    Problem,
    Run,
    RunEvent,
    RunStatus,
    SelectionDecision,
    Submission,
)
from packages.core.orchestration.state_machine import assert_run_transition
from packages.persistence.mappers import (
    agent_from_record,
    evaluation_from_record,
    generation_from_record,
    knowledge_from_record,
    lineage_from_record,
    model_call_from_record,
    model_profile_from_record,
    problem_from_record,
    run_event_from_record,
    run_from_record,
    selection_from_record,
    submission_from_record,
)
from packages.persistence.models import (
    AgentRecord,
    EvaluationRecord,
    GenerationRecord,
    KnowledgeItemRecord,
    LineageLinkRecord,
    ModelCallRecord,
    ModelProfileRecord,
    ProblemRecord,
    RunEventRecord,
    RunRecord,
    SelectionDecisionRecord,
    SubmissionRecord,
)


class ProblemSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, problem: Problem) -> Problem:
        record = ProblemRecord(id=problem.id, title=problem.title, prompt=problem.prompt)
        self.session.add(record)
        self.session.flush()
        return problem_from_record(record)

    def get(self, problem_id: UUID) -> Problem | None:
        record = self.session.get(ProblemRecord, problem_id)
        return problem_from_record(record) if record else None


class RunSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: Run) -> Run:
        record = RunRecord(
            id=run.id,
            problem_id=run.problem_id,
            status=run.status.value,
            max_generations=run.max_generations,
            population_size=run.population_size,
            survivor_count=run.survivor_count,
            fresh_agent_count=run.fresh_agent_count,
            redundancy_threshold=run.redundancy_threshold,
        )
        self.session.add(record)
        self.session.flush()
        return run_from_record(record)

    def get(self, run_id: UUID) -> Run | None:
        record = self.session.get(RunRecord, run_id)
        return run_from_record(record) if record else None

    def update_status(self, run_id: UUID, status: RunStatus) -> Run:
        record = self.session.get(RunRecord, run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        assert_run_transition(RunStatus(record.status), status)
        record.status = status.value
        self.session.flush()
        return run_from_record(record)


class GenerationSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, generation: Generation) -> Generation:
        record = GenerationRecord(
            id=generation.id,
            run_id=generation.run_id,
            index=generation.index,
        )
        self.session.add(record)
        self.session.flush()
        return generation_from_record(record)

    def get(self, generation_id: UUID) -> Generation | None:
        record = self.session.get(GenerationRecord, generation_id)
        return generation_from_record(record) if record else None

    def get_for_run(self, run_id: UUID, index: int) -> Generation | None:
        record = self.session.execute(
            select(GenerationRecord).where(
                GenerationRecord.run_id == run_id,
                GenerationRecord.index == index,
            )
        ).scalar_one_or_none()
        return generation_from_record(record) if record else None

    def list_for_run(self, run_id: UUID) -> list[Generation]:
        records = self.session.execute(
            select(GenerationRecord)
            .where(GenerationRecord.run_id == run_id)
            .order_by(GenerationRecord.index)
        ).scalars()
        return [generation_from_record(record) for record in records]


class AgentSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(self, agents: Iterable[Agent]) -> list[Agent]:
        records = [
            AgentRecord(
                id=agent.id,
                generation_id=agent.generation_id,
                role=agent.role,
                status=agent.status.value,
                niche=agent.niche.value,
                origin=agent.origin.value,
            )
            for agent in agents
        ]
        self.session.add_all(records)
        self.session.flush()
        return [agent_from_record(record) for record in records]

    def get(self, agent_id: UUID) -> Agent | None:
        record = self.session.get(AgentRecord, agent_id)
        return agent_from_record(record) if record else None

    def list_for_generation(self, generation_id: UUID) -> list[Agent]:
        records = self.session.execute(
            select(AgentRecord)
            .where(AgentRecord.generation_id == generation_id)
            .order_by(AgentRecord.created_at, AgentRecord.id)
        ).scalars()
        return [agent_from_record(record) for record in records]

    def update_status(self, agent_id: UUID, status: AgentStatus) -> Agent:
        record = self.session.get(AgentRecord, agent_id)
        if record is None:
            raise KeyError(f"Agent not found: {agent_id}")
        record.status = status.value
        self.session.flush()
        return agent_from_record(record)


class SubmissionSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, submission: Submission) -> Submission:
        record = SubmissionRecord(
            id=submission.id,
            agent_id=submission.agent_id,
            summary=submission.summary,
            approach=submission.approach,
            claims=[
                {
                    "statement": claim.statement,
                    "confidence": claim.confidence,
                    "support": claim.support,
                }
                for claim in submission.claims
            ],
            evidence=submission.evidence,
            discoveries=submission.discoveries,
            failed_attempts=submission.failed_attempts,
            open_questions=submission.open_questions,
            final_answer=submission.final_answer,
            raw_response=submission.raw_response,
        )
        self.session.add(record)
        self.session.flush()
        return submission_from_record(record)

    def get(self, submission_id: UUID) -> Submission | None:
        record = self.session.get(SubmissionRecord, submission_id)
        return submission_from_record(record) if record else None

    def get_for_agent(self, agent_id: UUID) -> Submission | None:
        record = self.session.execute(
            select(SubmissionRecord).where(SubmissionRecord.agent_id == agent_id)
        ).scalar_one_or_none()
        return submission_from_record(record) if record else None

    def list_for_generation(self, generation_id: UUID) -> list[Submission]:
        records = self.session.execute(
            select(SubmissionRecord)
            .join(AgentRecord, SubmissionRecord.agent_id == AgentRecord.id)
            .where(AgentRecord.generation_id == generation_id)
            .order_by(SubmissionRecord.created_at, SubmissionRecord.id)
        ).scalars()
        return [submission_from_record(record) for record in records]


class EvaluationSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, evaluation: Evaluation) -> Evaluation:
        record = EvaluationRecord(
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
        self.session.add(record)
        self.session.flush()
        return evaluation_from_record(record)

    def list_for_submission(self, submission_id: UUID) -> list[Evaluation]:
        records = self.session.execute(
            select(EvaluationRecord)
            .where(EvaluationRecord.submission_id == submission_id)
            .order_by(EvaluationRecord.created_at, EvaluationRecord.id)
        ).scalars()
        return [evaluation_from_record(record) for record in records]

    def list_for_generation(self, generation_id: UUID) -> list[Evaluation]:
        records = self.session.execute(
            select(EvaluationRecord)
            .join(SubmissionRecord, EvaluationRecord.submission_id == SubmissionRecord.id)
            .join(AgentRecord, SubmissionRecord.agent_id == AgentRecord.id)
            .where(AgentRecord.generation_id == generation_id)
            .order_by(EvaluationRecord.created_at, EvaluationRecord.id)
        ).scalars()
        return [evaluation_from_record(record) for record in records]


class SelectionSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(
        self,
        decisions: Iterable[SelectionDecision],
    ) -> list[SelectionDecision]:
        records = [
            SelectionDecisionRecord(
                id=decision.id,
                generation_id=decision.generation_id,
                submission_id=decision.submission_id,
                selected=decision.selected,
                rank=decision.rank,
                score_vector=decision.score_vector,
                reason=decision.reason,
                selection_kind=decision.selection_kind.value,
                novelty_score=decision.novelty_score,
                redundant_with_submission_id=decision.redundant_with_submission_id,
            )
            for decision in decisions
        ]
        self.session.add_all(records)
        self.session.flush()
        return [selection_from_record(record) for record in records]

    def list_for_generation(self, generation_id: UUID) -> list[SelectionDecision]:
        records = self.session.execute(
            select(SelectionDecisionRecord)
            .where(SelectionDecisionRecord.generation_id == generation_id)
            .order_by(SelectionDecisionRecord.rank)
        ).scalars()
        return [selection_from_record(record) for record in records]


class LineageSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(self, links: Iterable[LineageLink]) -> list[LineageLink]:
        records = [
            LineageLinkRecord(
                id=link.id,
                child_agent_id=link.child_agent_id,
                parent_submission_id=link.parent_submission_id,
                mutation_type=link.mutation_type.value,
            )
            for link in links
        ]
        self.session.add_all(records)
        self.session.flush()
        return [lineage_from_record(record) for record in records]

    def get_for_child(self, child_agent_id: UUID) -> LineageLink | None:
        record = self.session.execute(
            select(LineageLinkRecord).where(
                LineageLinkRecord.child_agent_id == child_agent_id
            )
        ).scalar_one_or_none()
        return lineage_from_record(record) if record else None

    def list_for_generation(self, generation_id: UUID) -> list[LineageLink]:
        records = self.session.execute(
            select(LineageLinkRecord)
            .join(AgentRecord, LineageLinkRecord.child_agent_id == AgentRecord.id)
            .where(AgentRecord.generation_id == generation_id)
            .order_by(LineageLinkRecord.created_at, LineageLinkRecord.id)
        ).scalars()
        return [lineage_from_record(record) for record in records]


class KnowledgeSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(self, items: Iterable[KnowledgeItem]) -> list[KnowledgeItem]:
        records = [
            KnowledgeItemRecord(
                id=item.id,
                run_id=item.run_id,
                generation_id=item.generation_id,
                submission_id=item.submission_id,
                kind=item.kind.value,
                content=item.content,
                status=item.status.value,
                confidence=item.confidence,
                provenance=item.provenance,
            )
            for item in items
        ]
        self.session.add_all(records)
        self.session.flush()
        return [knowledge_from_record(record) for record in records]

    def list_for_run(self, run_id: UUID) -> list[KnowledgeItem]:
        records = self.session.execute(
            select(KnowledgeItemRecord)
            .where(KnowledgeItemRecord.run_id == run_id)
            .order_by(KnowledgeItemRecord.created_at, KnowledgeItemRecord.id)
        ).scalars()
        return [knowledge_from_record(record) for record in records]

    def list_for_generation(self, generation_id: UUID) -> list[KnowledgeItem]:
        records = self.session.execute(
            select(KnowledgeItemRecord)
            .where(KnowledgeItemRecord.generation_id == generation_id)
            .order_by(KnowledgeItemRecord.created_at, KnowledgeItemRecord.id)
        ).scalars()
        return [knowledge_from_record(record) for record in records]


class ModelProfileSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, profile: ModelProfile) -> ModelProfile:
        record = ModelProfileRecord(
            id=profile.id,
            provider=profile.provider,
            model=profile.model,
            enabled=profile.enabled,
            profile_metadata=profile.metadata,
        )
        self.session.add(record)
        self.session.flush()
        return model_profile_from_record(record)

    def get(self, profile_id: UUID) -> ModelProfile | None:
        record = self.session.get(ModelProfileRecord, profile_id)
        return model_profile_from_record(record) if record else None

    def find(self, provider: str, model: str) -> ModelProfile | None:
        record = self.session.execute(
            select(ModelProfileRecord).where(
                ModelProfileRecord.provider == provider,
                ModelProfileRecord.model == model,
            )
        ).scalar_one_or_none()
        return model_profile_from_record(record) if record else None


class ModelCallSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, call: ModelCall) -> ModelCall:
        record = ModelCallRecord(
            id=call.id,
            model_profile_id=call.model_profile_id,
            run_id=call.run_id,
            agent_id=call.agent_id,
            task_type=call.task_type,
            status=call.status.value,
            latency_ms=call.latency_ms,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            estimated_cost=call.estimated_cost,
            retry_count=call.retry_count,
            request_metadata=call.request_metadata,
            response_metadata=call.response_metadata,
            error=call.error,
        )
        self.session.add(record)
        self.session.flush()
        return model_call_from_record(record)

    def get(self, call_id: UUID) -> ModelCall | None:
        record = self.session.get(ModelCallRecord, call_id)
        return model_call_from_record(record) if record else None


class RunEventSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, event: RunEvent) -> RunEvent:
        record = RunEventRecord(
            id=event.id,
            run_id=event.run_id,
            event_type=event.event_type,
            payload=event.payload,
        )
        self.session.add(record)
        self.session.flush()
        return run_event_from_record(record)

    def list_for_run(self, run_id: UUID, after_id: UUID | None = None) -> list[RunEvent]:
        query = select(RunEventRecord).where(RunEventRecord.run_id == run_id)
        if after_id is not None:
            anchor = self.session.get(RunEventRecord, after_id)
            if anchor is not None:
                query = query.where(
                    (RunEventRecord.created_at > anchor.created_at)
                    | (
                        (RunEventRecord.created_at == anchor.created_at)
                        & (RunEventRecord.id > anchor.id)
                    )
                )
        records = self.session.execute(
            query.order_by(RunEventRecord.created_at, RunEventRecord.id)
        ).scalars()
        return [run_event_from_record(record) for record in records]


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> Self:
        self.session = self.session_factory()
        self.problems = ProblemSqlRepository(self.session)
        self.runs = RunSqlRepository(self.session)
        self.generations = GenerationSqlRepository(self.session)
        self.agents = AgentSqlRepository(self.session)
        self.submissions = SubmissionSqlRepository(self.session)
        self.evaluations = EvaluationSqlRepository(self.session)
        self.selections = SelectionSqlRepository(self.session)
        self.lineages = LineageSqlRepository(self.session)
        self.knowledge = KnowledgeSqlRepository(self.session)
        self.model_profiles = ModelProfileSqlRepository(self.session)
        self.model_calls = ModelCallSqlRepository(self.session)
        self.events = RunEventSqlRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exc_type is not None:
            self.session.rollback()
        self.session.close()
        self.session = None

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work is not active")
        self.session.commit()

    def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work is not active")
        self.session.rollback()
