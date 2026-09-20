from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RESEARCHING = "RESEARCHING"
    JUDGING = "JUDGING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class AgentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentOrigin(StrEnum):
    INITIAL = "INITIAL"
    CLONED = "CLONED"
    FRESH = "FRESH"


class ResearchNiche(StrEnum):
    CONSTRUCTIVE = "CONSTRUCTIVE"
    SKEPTICAL = "SKEPTICAL"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    COMPUTATIONAL = "COMPUTATIONAL"
    SPECIAL_CASES = "SPECIAL_CASES"
    GENERALIZATION = "GENERALIZATION"
    ALTERNATIVE_FORMULATION = "ALTERNATIVE_FORMULATION"
    LEMMA_DECOMPOSITION = "LEMMA_DECOMPOSITION"


class MutationType(StrEnum):
    STRENGTHEN = "STRENGTHEN"
    FALSIFY = "FALSIFY"
    REDERIVE = "REDERIVE"
    GENERALIZE = "GENERALIZE"


class SelectionKind(StrEnum):
    ELITE = "ELITE"
    NOVELTY = "NOVELTY"
    WILDCARD = "WILDCARD"
    QUALITY = "QUALITY"
    REDUNDANT = "REDUNDANT"
    ELIMINATED = "ELIMINATED"


class KnowledgeKind(StrEnum):
    VERIFIED_FACT = "VERIFIED_FACT"
    LIKELY_FACT = "LIKELY_FACT"
    HYPOTHESIS = "HYPOTHESIS"
    CANDIDATE_LEMMA = "CANDIDATE_LEMMA"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    CONTRADICTION = "CONTRADICTION"
    FAILED_APPROACH = "FAILED_APPROACH"
    PROMISING_APPROACH = "PROMISING_APPROACH"
    UNRESOLVED_QUESTION = "UNRESOLVED_QUESTION"
    OBSERVATION = "OBSERVATION"
    CANDIDATE_SOLUTION = "CANDIDATE_SOLUTION"


class KnowledgeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"


class CrossPollinationKind(StrEnum):
    VERIFIED = "VERIFIED"
    PROMISING = "PROMISING"
    REFUTED = "REFUTED"
    OPEN = "OPEN"
    TRY = "TRY"


class CandidateLifecycle(StrEnum):
    PROPOSED = "PROPOSED"
    PROMISING = "PROMISING"
    LEADING = "LEADING"
    UNDER_ATTACK = "UNDER_ATTACK"
    VERIFICATION = "VERIFICATION"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"


class VerificationKind(StrEnum):
    STRUCTURED_EVIDENCE = "STRUCTURED_EVIDENCE"
    PYTHON_COMPILE = "PYTHON_COMPILE"
    ADVERSARIAL_CHECK = "ADVERSARIAL_CHECK"


class VerificationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class JobType(StrEnum):
    CREATE_GENERATION = "create_generation"
    RUN_RESEARCH_AGENT = "run_research_agent"
    START_JUDGING = "start_judging"
    RUN_JUDGE = "run_judge"
    RUN_CRITIC = "run_critic"
    FINALIZE_RUN = "finalize_run"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY = "RETRY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModelCallStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_STARTED = "RUN_STARTED"
    GENERATION_CREATED = "GENERATION_CREATED"
    AGENT_SPAWNED = "AGENT_SPAWNED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    JUDGING_STARTED = "JUDGING_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    DIVERSITY_ANALYZED = "DIVERSITY_ANALYZED"
    REDUNDANCY_DETECTED = "REDUNDANCY_DETECTED"
    SELECTION_COMPLETED = "SELECTION_COMPLETED"
    BRANCH_SELECTED = "BRANCH_SELECTED"
    BRANCH_ELIMINATED = "BRANCH_ELIMINATED"
    WILDCARD_SELECTED = "WILDCARD_SELECTED"
    AGENT_CLONED = "AGENT_CLONED"
    FRESH_AGENT_INJECTED = "FRESH_AGENT_INJECTED"
    KNOWLEDGE_CREATED = "KNOWLEDGE_CREATED"
    KNOWLEDGE_COMPACTED = "KNOWLEDGE_COMPACTED"
    CROSS_POLLINATION_CREATED = "CROSS_POLLINATION_CREATED"
    CRITIC_STARTED = "CRITIC_STARTED"
    CRITIC_COMPLETED = "CRITIC_COMPLETED"
    CANDIDATE_STATUS_CHANGED = "CANDIDATE_STATUS_CHANGED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_PASSED = "VERIFICATION_PASSED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_INCONCLUSIVE = "VERIFICATION_INCONCLUSIVE"
    ROUTING_DECISION = "ROUTING_DECISION"
    GENERATION_ADVANCED = "GENERATION_ADVANCED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"


@dataclass(slots=True)
class Problem:
    title: str
    prompt: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Run:
    problem_id: UUID
    status: RunStatus = RunStatus.CREATED
    max_generations: int = 1
    population_size: int = 4
    survivor_count: int = 2
    fresh_agent_count: int = 0
    redundancy_threshold: float = 0.78
    critic_count: int = 0
    verification_enabled: bool = False
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Generation:
    run_id: UUID
    index: int
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Agent:
    generation_id: UUID
    role: str
    status: AgentStatus = AgentStatus.PENDING
    niche: ResearchNiche = ResearchNiche.CONSTRUCTIVE
    origin: AgentOrigin = AgentOrigin.INITIAL
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ClaimDraft:
    statement: str
    confidence: float | None = None
    support: str | None = None


@dataclass(slots=True)
class Submission:
    agent_id: UUID
    summary: str
    approach: str
    claims: list[ClaimDraft] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    discoveries: list[str] = field(default_factory=list)
    failed_attempts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    final_answer: str | None = None
    raw_response: str = ""
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Evaluation:
    submission_id: UUID
    judge_agent_id: UUID
    correctness: float
    rigor: float
    novelty: float
    research_progress: float
    verifiability: float
    fatal_error: bool
    judge_confidence: float
    critique: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class SelectionDecision:
    generation_id: UUID
    submission_id: UUID
    selected: bool
    rank: int
    score_vector: dict[str, float | bool]
    reason: str
    selection_kind: SelectionKind = SelectionKind.ELIMINATED
    novelty_score: float = 0.0
    redundant_with_submission_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class LineageLink:
    child_agent_id: UUID
    parent_submission_id: UUID
    mutation_type: MutationType
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class KnowledgeItem:
    run_id: UUID
    generation_id: UUID
    submission_id: UUID | None
    kind: KnowledgeKind
    content: str
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    confidence: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class CrossPollinationPacket:
    run_id: UUID
    generation_id: UUID
    target_agent_id: UUID
    source_submission_id: UUID
    kind: CrossPollinationKind
    payload: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class CandidateState:
    generation_id: UUID
    submission_id: UUID
    status: CandidateLifecycle = CandidateLifecycle.PROPOSED
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class CriticFinding:
    generation_id: UUID
    critic_agent_id: UUID
    submission_id: UUID
    fatal_error: bool
    confidence: float
    critique: str
    counterexample: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class VerificationResult:
    run_id: UUID
    generation_id: UUID
    submission_id: UUID
    kind: VerificationKind
    status: VerificationStatus
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ModelProfile:
    provider: str
    model: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ModelState:
    model_profile_id: UUID
    quality_by_task: dict[str, float] = field(default_factory=dict)
    marginal_cash_cost: float = 0.0
    credit_cost: float = 0.0
    latency_ms: float = 1000.0
    scarcity: float = 0.0
    failure_rate: float = 0.0
    rate_limit_pressure: float = 0.0
    available_concurrency: int = 1
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ModelCall:
    model_profile_id: UUID
    task_type: str
    status: ModelCallStatus = ModelCallStatus.PENDING
    run_id: UUID | None = None
    agent_id: UUID | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None
    retry_count: int = 0
    request_metadata: dict[str, Any] = field(default_factory=dict)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Job:
    job_type: JobType
    payload: dict[str, Any]
    idempotency_key: str
    status: JobStatus = JobStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    available_at: datetime | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    claimed_by: str | None = None
    last_error: str | None = None
    completed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class RunEvent:
    run_id: UUID
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
