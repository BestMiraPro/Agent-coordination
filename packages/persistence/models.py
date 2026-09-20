from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.core.domain.models import (
    AgentOrigin,
    AgentStatus,
    CandidateLifecycle,
    EngineeringStatus,
    JobStatus,
    KnowledgeStatus,
    ModelCallStatus,
    ResearchNiche,
    RunStatus,
    SelectionKind,
    VerificationStatus,
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectRecord(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")


class ProblemRecord(TimestampMixin, Base):
    __tablename__ = "problems"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )


class RunRecord(TimestampMixin, Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("max_generations > 0", name="ck_run_max_generations_positive"),
        CheckConstraint("population_size > 1", name="ck_run_population_size"),
        CheckConstraint("survivor_count > 0", name="ck_run_survivor_count_positive"),
        CheckConstraint("survivor_count < population_size", name="ck_run_survivors_lt_population"),
        CheckConstraint("fresh_agent_count >= 0", name="ck_run_fresh_nonnegative"),
        CheckConstraint("fresh_agent_count < population_size", name="ck_run_fresh_lt_population"),
        CheckConstraint(
            "redundancy_threshold >= 0 AND redundancy_threshold <= 1",
            name="ck_run_redundancy_threshold",
        ),
        CheckConstraint("critic_count >= 0", name="ck_run_critic_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    problem_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RunStatus.CREATED.value, server_default=RunStatus.CREATED.value
    )
    max_generations: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    population_size: Mapped[int] = mapped_column(Integer, nullable=False, default=4, server_default="4")
    survivor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    fresh_agent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    redundancy_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.78, server_default="0.78")
    critic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    verification_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class GenerationRecord(TimestampMixin, Base):
    __tablename__ = "generations"
    __table_args__ = (UniqueConstraint("run_id", "index", name="uq_generation_run_index"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)


class AgentRecord(TimestampMixin, Base):
    __tablename__ = "agents"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AgentStatus.PENDING.value, server_default=AgentStatus.PENDING.value
    )
    niche: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ResearchNiche.CONSTRUCTIVE.value,
        server_default=ResearchNiche.CONSTRUCTIVE.value,
    )
    origin: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AgentOrigin.INITIAL.value,
        server_default=AgentOrigin.INITIAL.value,
    )


class SubmissionRecord(TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("agent_id", name="uq_submission_agent"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    approach: Mapped[str] = mapped_column(Text, nullable=False)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    discoveries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    failed_attempts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    open_questions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")


class EvaluationRecord(TimestampMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("submission_id", "judge_agent_id", name="uq_evaluation_submission_judge"),
        CheckConstraint("correctness >= 0 AND correctness <= 1", name="ck_eval_correctness"),
        CheckConstraint("rigor >= 0 AND rigor <= 1", name="ck_eval_rigor"),
        CheckConstraint("novelty >= 0 AND novelty <= 1", name="ck_eval_novelty"),
        CheckConstraint("research_progress >= 0 AND research_progress <= 1", name="ck_eval_progress"),
        CheckConstraint("verifiability >= 0 AND verifiability <= 1", name="ck_eval_verifiability"),
        CheckConstraint("judge_confidence >= 0 AND judge_confidence <= 1", name="ck_eval_confidence"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    judge_agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    correctness: Mapped[float] = mapped_column(Float, nullable=False)
    rigor: Mapped[float] = mapped_column(Float, nullable=False)
    novelty: Mapped[float] = mapped_column(Float, nullable=False)
    research_progress: Mapped[float] = mapped_column(Float, nullable=False)
    verifiability: Mapped[float] = mapped_column(Float, nullable=False)
    fatal_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    judge_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    critique: Mapped[str] = mapped_column(Text, nullable=False)


class SelectionDecisionRecord(TimestampMixin, Base):
    __tablename__ = "selection_decisions"
    __table_args__ = (
        UniqueConstraint("generation_id", "submission_id", name="uq_selection_generation_submission"),
        CheckConstraint("rank > 0", name="ck_selection_rank_positive"),
        CheckConstraint(
            "novelty_score >= 0 AND novelty_score <= 1",
            name="ck_selection_novelty_score",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score_vector: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    selection_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SelectionKind.ELIMINATED.value,
        server_default=SelectionKind.ELIMINATED.value,
    )
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    redundant_with_submission_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class LineageLinkRecord(TimestampMixin, Base):
    __tablename__ = "lineage_links"
    __table_args__ = (
        UniqueConstraint("child_agent_id", name="uq_lineage_child_agent"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    child_agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mutation_type: Mapped[str] = mapped_column(String(32), nullable=False)


class KnowledgeItemRecord(TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        Index("ix_knowledge_items_run_kind", "run_id", "kind"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=KnowledgeStatus.ACTIVE.value,
        server_default=KnowledgeStatus.ACTIVE.value,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CrossPollinationPacketRecord(TimestampMixin, Base):
    __tablename__ = "cross_pollination_packets"
    __table_args__ = (
        UniqueConstraint(
            "target_agent_id",
            "source_submission_id",
            name="uq_cross_pollination_target_source",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CandidateStateRecord(TimestampMixin, Base):
    __tablename__ = "candidate_states"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_candidate_state_submission"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CandidateLifecycle.PROPOSED.value,
        server_default=CandidateLifecycle.PROPOSED.value,
    )


class CriticFindingRecord(TimestampMixin, Base):
    __tablename__ = "critic_findings"
    __table_args__ = (
        UniqueConstraint(
            "critic_agent_id",
            "submission_id",
            name="uq_critic_finding_agent_submission",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_critic_confidence",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    critic_agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fatal_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    critique: Mapped[str] = mapped_column(Text, nullable=False)
    counterexample: Mapped[str | None] = mapped_column(Text, nullable=True)


class VerificationResultRecord(TimestampMixin, Base):
    __tablename__ = "verification_results"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "kind",
            name="uq_verification_submission_kind",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=VerificationStatus.INCONCLUSIVE.value,
        server_default=VerificationStatus.INCONCLUSIVE.value,
    )
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    result_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class EngineeringRunRecord(TimestampMixin, Base):
    __tablename__ = "engineering_runs"
    __table_args__ = (
        CheckConstraint("repair_count >= 0", name="ck_engineering_repair_count"),
        CheckConstraint("max_repairs >= 0", name="ck_engineering_max_repairs"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EngineeringStatus.CREATED.value,
        server_default=EngineeringStatus.CREATED.value,
    )
    repair_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_repairs: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")


class EngineeringArtifactRecord(TimestampMixin, Base):
    __tablename__ = "engineering_artifacts"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    engineering_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("engineering_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    repair_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class EngineeringCheckRecord(TimestampMixin, Base):
    __tablename__ = "engineering_checks"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    engineering_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("engineering_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    repair_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ModelProfileRecord(TimestampMixin, Base):
    __tablename__ = "model_profiles"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_model_profile_provider_model"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    profile_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class ModelStateRecord(TimestampMixin, Base):
    __tablename__ = "model_states"
    __table_args__ = (
        UniqueConstraint("model_profile_id", name="uq_model_state_profile"),
        CheckConstraint("failure_rate >= 0 AND failure_rate <= 1", name="ck_model_state_failure"),
        CheckConstraint(
            "rate_limit_pressure >= 0 AND rate_limit_pressure <= 1",
            name="ck_model_state_rate_pressure",
        ),
        CheckConstraint("scarcity >= 0 AND scarcity <= 1", name="ck_model_state_scarcity"),
        CheckConstraint("available_concurrency >= 0", name="ck_model_state_concurrency"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quality_by_task: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    marginal_cash_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    credit_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0, server_default="1000")
    scarcity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    rate_limit_pressure: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    available_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class ModelCallRecord(TimestampMixin, Base):
    __tablename__ = "model_calls"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    engineering_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("engineering_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ModelCallStatus.PENDING.value, server_default=ModelCallStatus.PENDING.value
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    request_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    response_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobRecord(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("attempt >= 0", name="ck_job_attempt_nonnegative"),
        CheckConstraint("max_attempts > 0", name="ck_job_max_attempts_positive"),
        Index("ix_jobs_claimable", "status", "available_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobStatus.PENDING.value, server_default=JobStatus.PENDING.value
    )
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEventRecord(Base):
    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_created", "run_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
