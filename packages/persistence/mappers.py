from __future__ import annotations

from packages.core.domain.models import (
    Agent, AgentStatus, ClaimDraft, Evaluation, Generation, Job, JobStatus, JobType,
    ModelCall, ModelCallStatus, ModelProfile, Problem, Run, RunEvent, RunStatus, Submission,
)
from packages.persistence.models import (
    AgentRecord, EvaluationRecord, GenerationRecord, JobRecord, ModelCallRecord,
    ModelProfileRecord, ProblemRecord, RunEventRecord, RunRecord, SubmissionRecord,
)


def problem_from_record(record: ProblemRecord) -> Problem:
    return Problem(id=record.id, title=record.title, prompt=record.prompt)


def run_from_record(record: RunRecord) -> Run:
    return Run(id=record.id, problem_id=record.problem_id, status=RunStatus(record.status))


def generation_from_record(record: GenerationRecord) -> Generation:
    return Generation(id=record.id, run_id=record.run_id, index=record.index)


def agent_from_record(record: AgentRecord) -> Agent:
    return Agent(id=record.id, generation_id=record.generation_id, role=record.role, status=AgentStatus(record.status))


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


def model_profile_from_record(record: ModelProfileRecord) -> ModelProfile:
    return ModelProfile(id=record.id, provider=record.provider, model=record.model, enabled=record.enabled, metadata=dict(record.profile_metadata))


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
    return RunEvent(id=record.id, run_id=record.run_id, event_type=record.event_type, payload=dict(record.payload), created_at=record.created_at)
