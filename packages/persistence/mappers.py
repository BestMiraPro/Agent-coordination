from __future__ import annotations

from packages.core.domain.models import (
    Agent,
    AgentOrigin,
    AgentStatus,
    CandidateLifecycle,
    CandidateState,
    ClaimDraft,
    CriticFinding,
    CrossPollinationKind,
    CrossPollinationPacket,
    Evaluation,
    Generation,
    Job,
    JobStatus,
    JobType,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    LineageLink,
    ModelCall,
    ModelCallStatus,
    ModelProfile,
    ModelState,
    MutationType,
    Problem,
    Project,
    ResearchNiche,
    Run,
    RunEvent,
    RunStatus,
    SelectionDecision,
    SelectionKind,
    Submission,
    VerificationKind,
    VerificationResult,
    VerificationStatus,
)
from packages.persistence.models import (
    AgentRecord,
    CandidateStateRecord,
    CriticFindingRecord,
    CrossPollinationPacketRecord,
    EvaluationRecord,
    GenerationRecord,
    JobRecord,
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


def project_from_record(record: ProjectRecord) -> Project:
    return Project(
        id=record.id,
        name=record.name,
        description=record.description,
    )


def problem_from_record(record: ProblemRecord) -> Problem:
    return Problem(
        id=record.id,
        title=record.title,
        prompt=record.prompt,
        project_id=record.project_id,
    )


def run_from_record(record: RunRecord) -> Run:
    return Run(
        id=record.id,
        problem_id=record.problem_id,
        status=RunStatus(record.status),
        max_generations=record.max_generations,
        population_size=record.population_size,
        survivor_count=record.survivor_count,
        fresh_agent_count=record.fresh_agent_count,
        redundancy_threshold=record.redundancy_threshold,
        critic_count=record.critic_count,
        verification_enabled=record.verification_enabled,
    )


def generation_from_record(record: GenerationRecord) -> Generation:
    return Generation(id=record.id, run_id=record.run_id, index=record.index)


def agent_from_record(record: AgentRecord) -> Agent:
    return Agent(
        id=record.id,
        generation_id=record.generation_id,
        role=record.role,
        status=AgentStatus(record.status),
        niche=ResearchNiche(record.niche),
        origin=AgentOrigin(record.origin),
    )


def submission_from_record(record: SubmissionRecord) -> Submission:
    return Submission(
        id=record.id,
        agent_id=record.agent_id,
        summary=record.summary,
        approach=record.approach,
        claims=[ClaimDraft(**claim) for claim in record.claims],
        evidence=list(record.evidence),
        discoveries=list(record.discoveries),
        failed_attempts=list(record.failed_attempts),
        open_questions=list(record.open_questions),
        final_answer=record.final_answer,
        raw_response=record.raw_response,
    )


def evaluation_from_record(record: EvaluationRecord) -> Evaluation:
    return Evaluation(
        id=record.id,
        submission_id=record.submission_id,
        judge_agent_id=record.judge_agent_id,
        correctness=record.correctness,
        rigor=record.rigor,
        novelty=record.novelty,
        research_progress=record.research_progress,
        verifiability=record.verifiability,
        fatal_error=record.fatal_error,
        judge_confidence=record.judge_confidence,
        critique=record.critique,
    )


def selection_from_record(record: SelectionDecisionRecord) -> SelectionDecision:
    return SelectionDecision(
        id=record.id,
        generation_id=record.generation_id,
        submission_id=record.submission_id,
        selected=record.selected,
        rank=record.rank,
        score_vector=dict(record.score_vector),
        reason=record.reason,
        selection_kind=SelectionKind(record.selection_kind),
        novelty_score=record.novelty_score,
        redundant_with_submission_id=record.redundant_with_submission_id,
    )


def lineage_from_record(record: LineageLinkRecord) -> LineageLink:
    return LineageLink(
        id=record.id,
        child_agent_id=record.child_agent_id,
        parent_submission_id=record.parent_submission_id,
        mutation_type=MutationType(record.mutation_type),
    )


def candidate_state_from_record(record: CandidateStateRecord) -> CandidateState:
    return CandidateState(
        id=record.id,
        generation_id=record.generation_id,
        submission_id=record.submission_id,
        status=CandidateLifecycle(record.status),
    )


def critic_finding_from_record(record: CriticFindingRecord) -> CriticFinding:
    return CriticFinding(
        id=record.id,
        generation_id=record.generation_id,
        critic_agent_id=record.critic_agent_id,
        submission_id=record.submission_id,
        fatal_error=record.fatal_error,
        confidence=record.confidence,
        critique=record.critique,
        counterexample=record.counterexample,
    )


def cross_pollination_from_record(
    record: CrossPollinationPacketRecord,
) -> CrossPollinationPacket:
    return CrossPollinationPacket(
        id=record.id,
        run_id=record.run_id,
        generation_id=record.generation_id,
        target_agent_id=record.target_agent_id,
        source_submission_id=record.source_submission_id,
        kind=CrossPollinationKind(record.kind),
        payload=dict(record.payload),
    )


def knowledge_from_record(record: KnowledgeItemRecord) -> KnowledgeItem:
    return KnowledgeItem(
        id=record.id,
        run_id=record.run_id,
        generation_id=record.generation_id,
        submission_id=record.submission_id,
        kind=KnowledgeKind(record.kind),
        content=record.content,
        status=KnowledgeStatus(record.status),
        confidence=record.confidence,
        provenance=dict(record.provenance),
    )


def verification_from_record(record: VerificationResultRecord) -> VerificationResult:
    return VerificationResult(
        id=record.id,
        run_id=record.run_id,
        generation_id=record.generation_id,
        submission_id=record.submission_id,
        kind=VerificationKind(record.kind),
        status=VerificationStatus(record.status),
        detail=record.detail,
        metadata=dict(record.result_metadata),
    )


def model_profile_from_record(record: ModelProfileRecord) -> ModelProfile:
    return ModelProfile(
        id=record.id,
        provider=record.provider,
        model=record.model,
        enabled=record.enabled,
        metadata=dict(record.profile_metadata),
    )


def model_state_from_record(record: ModelStateRecord) -> ModelState:
    return ModelState(
        id=record.id,
        model_profile_id=record.model_profile_id,
        quality_by_task={
            str(key): float(value)
            for key, value in dict(record.quality_by_task).items()
        },
        marginal_cash_cost=record.marginal_cash_cost,
        credit_cost=record.credit_cost,
        latency_ms=record.latency_ms,
        scarcity=record.scarcity,
        failure_rate=record.failure_rate,
        rate_limit_pressure=record.rate_limit_pressure,
        available_concurrency=record.available_concurrency,
        enabled=record.enabled,
    )


def model_call_from_record(record: ModelCallRecord) -> ModelCall:
    return ModelCall(
        id=record.id,
        model_profile_id=record.model_profile_id,
        task_type=record.task_type,
        status=ModelCallStatus(record.status),
        run_id=record.run_id,
        agent_id=record.agent_id,
        latency_ms=record.latency_ms,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        estimated_cost=record.estimated_cost,
        retry_count=record.retry_count,
        request_metadata=dict(record.request_metadata),
        response_metadata=dict(record.response_metadata),
        error=record.error,
    )


def job_from_record(record: JobRecord) -> Job:
    return Job(
        id=record.id,
        job_type=JobType(record.job_type),
        payload=dict(record.payload),
        idempotency_key=record.idempotency_key,
        status=JobStatus(record.status),
        attempt=record.attempt,
        max_attempts=record.max_attempts,
        available_at=record.available_at,
        claimed_at=record.claimed_at,
        lease_expires_at=record.lease_expires_at,
        claimed_by=record.claimed_by,
        last_error=record.last_error,
        completed_at=record.completed_at,
    )


def run_event_from_record(record: RunEventRecord) -> RunEvent:
    return RunEvent(
        id=record.id,
        run_id=record.run_id,
        event_type=record.event_type,
        payload=dict(record.payload),
        created_at=record.created_at,
    )
