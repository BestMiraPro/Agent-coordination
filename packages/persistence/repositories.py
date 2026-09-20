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
    CandidateLifecycle,
    CandidateState,
    CriticFinding,
    CrossPollinationPacket,
    Evaluation,
    Generation,
    KnowledgeItem,
    LineageLink,
    ModelCall,
    ModelProfile,
    ModelState,
    Problem,
    Project,
    Run,
    RunEvent,
    RunStatus,
    SelectionDecision,
    Submission,
    VerificationResult,
)
from packages.core.orchestration.state_machine import assert_run_transition
from packages.persistence.mappers import (
    agent_from_record,
    candidate_state_from_record,
    critic_finding_from_record,
    cross_pollination_from_record,
    evaluation_from_record,
    generation_from_record,
    knowledge_from_record,
    lineage_from_record,
    model_call_from_record,
    model_profile_from_record,
    model_state_from_record,
    problem_from_record,
    project_from_record,
    run_event_from_record,
    run_from_record,
    selection_from_record,
    submission_from_record,
    verification_from_record,
)
from packages.persistence.models import (
    AgentRecord,
    CandidateStateRecord,
    CriticFindingRecord,
    CrossPollinationPacketRecord,
    EvaluationRecord,
    GenerationRecord,
    KnowledgeItemRecord,
    LineageLinkRecord,
    ModelCallRecord,
    ModelProfileRecord,
    ModelStateRecord,
    ProblemRecord,
    ProjectRecord,
    RunEventRecord,
    RunRecord,
    SelectionDecisionRecord,
    SubmissionRecord,
    VerificationResultRecord,
)


class ProjectSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, project: Project) -> Project:
        record = ProjectRecord(
            id=project.id,
            name=project.name,
            description=project.description,
        )
        self.session.add(record)
        self.session.flush()
        return project_from_record(record)

    def get(self, project_id: UUID) -> Project | None:
        record = self.session.get(ProjectRecord, project_id)
        return project_from_record(record) if record else None

    def list_all(self) -> list[Project]:
        records = self.session.execute(
            select(ProjectRecord).order_by(ProjectRecord.created_at, ProjectRecord.id)
        ).scalars()
        return [project_from_record(record) for record in records]


class ProblemSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, problem: Problem) -> Problem:
        record = ProblemRecord(
            id=problem.id,
            title=problem.title,
            prompt=problem.prompt,
            project_id=problem.project_id,
        )
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
            critic_count=run.critic_count,
            verification_enabled=run.verification_enabled,
        )
        self.session.add(record)
        self.session.flush()
        return run_from_record(record)

    def get(self, run_id: UUID) -> Run | None:
        record = self.session.get(RunRecord, run_id)
        return run_from_record(record) if record else None

    def list_all(self) -> list[Run]:
        records = self.session.execute(
            select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id)
        ).scalars()
        return [run_from_record(record) for record in records]

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


class CandidateStateSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(self, states: Iterable[CandidateState]) -> list[CandidateState]:
        records = [
            CandidateStateRecord(
                id=state.id,
                generation_id=state.generation_id,
                submission_id=state.submission_id,
                status=state.status.value,
            )
            for state in states
        ]
        self.session.add_all(records)
        self.session.flush()
        return [candidate_state_from_record(record) for record in records]

    def get_for_submission(self, submission_id: UUID) -> CandidateState | None:
        record = self.session.execute(
            select(CandidateStateRecord).where(
                CandidateStateRecord.submission_id == submission_id
            )
        ).scalar_one_or_none()
        return candidate_state_from_record(record) if record else None

    def list_for_generation(self, generation_id: UUID) -> list[CandidateState]:
        records = self.session.execute(
            select(CandidateStateRecord)
            .where(CandidateStateRecord.generation_id == generation_id)
            .order_by(CandidateStateRecord.created_at, CandidateStateRecord.id)
        ).scalars()
        return [candidate_state_from_record(record) for record in records]

    def update_status(
        self,
        submission_id: UUID,
        status: CandidateLifecycle,
    ) -> CandidateState:
        record = self.session.execute(
            select(CandidateStateRecord).where(
                CandidateStateRecord.submission_id == submission_id
            )
        ).scalar_one_or_none()
        if record is None:
            raise KeyError(f"Candidate state not found: {submission_id}")
        record.status = status.value
        self.session.flush()
        return candidate_state_from_record(record)


class CriticFindingSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, finding: CriticFinding) -> CriticFinding:
        record = CriticFindingRecord(
            id=finding.id,
            generation_id=finding.generation_id,
            critic_agent_id=finding.critic_agent_id,
            submission_id=finding.submission_id,
            fatal_error=finding.fatal_error,
            confidence=finding.confidence,
            critique=finding.critique,
            counterexample=finding.counterexample,
        )
        self.session.add(record)
        self.session.flush()
        return critic_finding_from_record(record)

    def get_for_agent_submission(
        self,
        critic_agent_id: UUID,
        submission_id: UUID,
    ) -> CriticFinding | None:
        record = self.session.execute(
            select(CriticFindingRecord).where(
                CriticFindingRecord.critic_agent_id == critic_agent_id,
                CriticFindingRecord.submission_id == submission_id,
            )
        ).scalar_one_or_none()
        return critic_finding_from_record(record) if record else None

    def list_for_generation(self, generation_id: UUID) -> list[CriticFinding]:
        records = self.session.execute(
            select(CriticFindingRecord)
            .where(CriticFindingRecord.generation_id == generation_id)
            .order_by(CriticFindingRecord.created_at, CriticFindingRecord.id)
        ).scalars()
        return [critic_finding_from_record(record) for record in records]


class CrossPollinationSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(
        self,
        packets: Iterable[CrossPollinationPacket],
    ) -> list[CrossPollinationPacket]:
        records = [
            CrossPollinationPacketRecord(
                id=packet.id,
                run_id=packet.run_id,
                generation_id=packet.generation_id,
                target_agent_id=packet.target_agent_id,
                source_submission_id=packet.source_submission_id,
                kind=packet.kind.value,
                payload=packet.payload,
            )
            for packet in packets
        ]
        self.session.add_all(records)
        self.session.flush()
        return [cross_pollination_from_record(record) for record in records]

    def list_for_agent(self, agent_id: UUID) -> list[CrossPollinationPacket]:
        records = self.session.execute(
            select(CrossPollinationPacketRecord)
            .where(CrossPollinationPacketRecord.target_agent_id == agent_id)
            .order_by(CrossPollinationPacketRecord.created_at, CrossPollinationPacketRecord.id)
        ).scalars()
        return [cross_pollination_from_record(record) for record in records]

    def list_for_generation(self, generation_id: UUID) -> list[CrossPollinationPacket]:
        records = self.session.execute(
            select(CrossPollinationPacketRecord)
            .where(CrossPollinationPacketRecord.generation_id == generation_id)
            .order_by(CrossPollinationPacketRecord.created_at, CrossPollinationPacketRecord.id)
        ).scalars()
        return [cross_pollination_from_record(record) for record in records]


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


class VerificationSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(
        self,
        results: Iterable[VerificationResult],
    ) -> list[VerificationResult]:
        records = [
            VerificationResultRecord(
                id=result.id,
                run_id=result.run_id,
                generation_id=result.generation_id,
                submission_id=result.submission_id,
                kind=result.kind.value,
                status=result.status.value,
                detail=result.detail,
                result_metadata=result.metadata,
            )
            for result in results
        ]
        self.session.add_all(records)
        self.session.flush()
        return [verification_from_record(record) for record in records]

    def list_for_submission(self, submission_id: UUID) -> list[VerificationResult]:
        records = self.session.execute(
            select(VerificationResultRecord)
            .where(VerificationResultRecord.submission_id == submission_id)
            .order_by(VerificationResultRecord.created_at, VerificationResultRecord.id)
        ).scalars()
        return [verification_from_record(record) for record in records]

    def list_for_generation(self, generation_id: UUID) -> list[VerificationResult]:
        records = self.session.execute(
            select(VerificationResultRecord)
            .where(VerificationResultRecord.generation_id == generation_id)
            .order_by(VerificationResultRecord.created_at, VerificationResultRecord.id)
        ).scalars()
        return [verification_from_record(record) for record in records]


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


class ModelStateSqlRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, state: ModelState) -> ModelState:
        record = ModelStateRecord(
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
        self.session.add(record)
        self.session.flush()
        return model_state_from_record(record)

    def get_for_profile(self, model_profile_id: UUID) -> ModelState | None:
        record = self.session.execute(
            select(ModelStateRecord).where(
                ModelStateRecord.model_profile_id == model_profile_id
            )
        ).scalar_one_or_none()
        return model_state_from_record(record) if record else None

    def list_all(self) -> list[ModelState]:
        records = self.session.execute(
            select(ModelStateRecord).order_by(
                ModelStateRecord.created_at,
                ModelStateRecord.id,
            )
        ).scalars()
        return [model_state_from_record(record) for record in records]

    def observe_call(
        self,
        model_profile_id: UUID,
        *,
        success: bool,
        latency_ms: int | None,
    ) -> ModelState | None:
        record = self.session.execute(
            select(ModelStateRecord).where(
                ModelStateRecord.model_profile_id == model_profile_id
            )
        ).scalar_one_or_none()
        if record is None:
            return None
        observation = 0.0 if success else 1.0
        record.failure_rate = max(
            0.0,
            min(1.0, 0.9 * record.failure_rate + 0.1 * observation),
        )
        if latency_ms is not None:
            record.latency_ms = max(
                0.0,
                0.8 * record.latency_ms + 0.2 * float(latency_ms),
            )
        self.session.flush()
        return model_state_from_record(record)


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

    def list_for_run(self, run_id: UUID) -> list[ModelCall]:
        records = self.session.execute(
            select(ModelCallRecord)
            .where(ModelCallRecord.run_id == run_id)
            .order_by(ModelCallRecord.created_at, ModelCallRecord.id)
        ).scalars()
        return [model_call_from_record(record) for record in records]


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
        self.projects = ProjectSqlRepository(self.session)
        self.problems = ProblemSqlRepository(self.session)
        self.runs = RunSqlRepository(self.session)
        self.generations = GenerationSqlRepository(self.session)
        self.agents = AgentSqlRepository(self.session)
        self.submissions = SubmissionSqlRepository(self.session)
        self.evaluations = EvaluationSqlRepository(self.session)
        self.selections = SelectionSqlRepository(self.session)
        self.lineages = LineageSqlRepository(self.session)
        self.candidate_states = CandidateStateSqlRepository(self.session)
        self.critic_findings = CriticFindingSqlRepository(self.session)
        self.cross_pollination = CrossPollinationSqlRepository(self.session)
        self.knowledge = KnowledgeSqlRepository(self.session)
        self.verifications = VerificationSqlRepository(self.session)
        self.model_profiles = ModelProfileSqlRepository(self.session)
        self.model_states = ModelStateSqlRepository(self.session)
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
