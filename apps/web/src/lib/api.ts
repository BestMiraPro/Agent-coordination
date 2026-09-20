export type RunStatus =
  | "CREATED"
  | "RESEARCHING"
  | "JUDGING"
  | "COMPLETED"
  | "PAUSED"
  | "FAILED";

export type AgentStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
export type AgentOrigin = "INITIAL" | "CLONED" | "FRESH";
export type CandidateLifecycle =
  | "PROPOSED"
  | "PROMISING"
  | "LEADING"
  | "UNDER_ATTACK"
  | "VERIFICATION"
  | "VERIFIED"
  | "REFUTED";
export type ResearchNiche =
  | "CONSTRUCTIVE"
  | "SKEPTICAL"
  | "COUNTEREXAMPLE"
  | "COMPUTATIONAL"
  | "SPECIAL_CASES"
  | "GENERALIZATION"
  | "ALTERNATIVE_FORMULATION"
  | "LEMMA_DECOMPOSITION";
export type MutationType =
  | "STRENGTHEN"
  | "FALSIFY"
  | "REDERIVE"
  | "GENERALIZE";
export type SelectionKind =
  | "ELITE"
  | "NOVELTY"
  | "WILDCARD"
  | "QUALITY"
  | "REDUNDANT"
  | "ELIMINATED";
export type KnowledgeKind =
  | "VERIFIED_FACT"
  | "LIKELY_FACT"
  | "HYPOTHESIS"
  | "CANDIDATE_LEMMA"
  | "COUNTEREXAMPLE"
  | "CONTRADICTION"
  | "FAILED_APPROACH"
  | "PROMISING_APPROACH"
  | "UNRESOLVED_QUESTION"
  | "OBSERVATION"
  | "CANDIDATE_SOLUTION";
export type VerificationStatus = "PASSED" | "FAILED" | "INCONCLUSIVE";

export type EngineeringStatus =
  | "CREATED"
  | "PLANNING"
  | "IMPLEMENTING"
  | "TESTING"
  | "REVIEWING"
  | "REPAIRING"
  | "COMPLETED"
  | "FAILED";

export type EngineeringStage = "PLAN" | "IMPLEMENTATION" | "REPAIR" | "REVIEW";

export type Project = { id: string; name: string; description: string };

export type Claim = {
  statement: string;
  confidence: number | null;
  support: string | null;
};

export type Submission = {
  id: string;
  agent_id: string;
  summary: string;
  approach: string;
  claims: Claim[];
  evidence: string[];
  discoveries: string[];
  failed_attempts: string[];
  open_questions: string[];
  final_answer: string | null;
  raw_response: string;
};

export type Evaluation = {
  id: string;
  submission_id: string;
  judge_agent_id: string;
  correctness: number;
  rigor: number;
  novelty: number;
  research_progress: number;
  verifiability: number;
  fatal_error: boolean;
  judge_confidence: number;
  critique: string;
};

export type SelectionDecision = {
  id: string;
  submission_id: string;
  selected: boolean;
  rank: number;
  score_vector: Record<string, number | boolean>;
  reason: string;
  selection_kind: SelectionKind;
  novelty_score: number;
  redundant_with_submission_id: string | null;
};

export type Lineage = {
  id: string;
  child_agent_id: string;
  parent_submission_id: string;
  mutation_type: MutationType;
};

export type CrossPollination = {
  id: string;
  target_agent_id: string;
  source_submission_id: string;
  kind: string;
  payload: Record<string, unknown>;
};

export type Knowledge = {
  id: string;
  generation_id: string;
  submission_id: string | null;
  kind: KnowledgeKind;
  content: string;
  status: string;
  confidence: number | null;
  provenance: Record<string, unknown>;
};

export type CandidateState = {
  id: string;
  submission_id: string;
  status: CandidateLifecycle;
};

export type CriticFinding = {
  id: string;
  critic_agent_id: string;
  submission_id: string;
  fatal_error: boolean;
  confidence: number;
  critique: string;
  counterexample: string | null;
};

export type Verification = {
  id: string;
  submission_id: string;
  kind: string;
  status: VerificationStatus;
  detail: string;
  metadata: Record<string, unknown>;
};

export type Agent = {
  id: string;
  role: string;
  status: AgentStatus;
  niche: ResearchNiche;
  origin: AgentOrigin;
};

export type Generation = {
  id: string;
  index: number;
  agents: Agent[];
  submissions: Submission[];
  evaluations: Evaluation[];
  selections: SelectionDecision[];
  lineages: Lineage[];
  cross_pollination: CrossPollination[];
  knowledge: Knowledge[];
  candidate_states: CandidateState[];
  critic_findings: CriticFinding[];
  verifications: Verification[];
};

export type RunDetail = {
  id: string;
  status: RunStatus;
  max_generations: number;
  population_size: number;
  survivor_count: number;
  fresh_agent_count: number;
  redundancy_threshold: number;
  critic_count: number;
  verification_enabled: boolean;
  problem: {
    id: string;
    title: string;
    prompt: string;
    project_id: string | null;
  };
  generations: Generation[];
};

export type RunMetrics = {
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  generations: number;
  knowledge_items: number;
  verifications: number;
  verified_candidates: number;
  active_niches: number;
  judge_disagreement: number;
};

export type ModelState = {
  id: string;
  model_profile_id: string;
  quality_by_task: Record<string, number>;
  marginal_cash_cost: number;
  credit_cost: number;
  latency_ms: number;
  scarcity: number;
  failure_rate: number;
  rate_limit_pressure: number;
  available_concurrency: number;
  enabled: boolean;
};

export type RunEvent = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
};

export type EngineeringArtifact = {
  id: string;
  stage: EngineeringStage;
  role: string;
  content: Record<string, unknown>;
  repair_cycle: number;
};

export type EngineeringCheck = {
  id: string;
  name: string;
  passed: boolean;
  detail: string;
  repair_cycle: number;
};

export type EngineeringRun = {
  id: string;
  project_id: string | null;
  title: string;
  objective: string;
  status: EngineeringStatus;
  repair_count: number;
  max_repairs: number;
};

export type EngineeringRunDetail = EngineeringRun & {
  artifacts: EngineeringArtifact[];
  checks: EngineeringCheck[];
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createProject(name: string, description = "") {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function listProjects() {
  return request<Project[]>("/projects", { cache: "no-store" });
}

export async function createProblem(
  title: string,
  prompt: string,
  projectId?: string,
) {
  return request<{ id: string; title: string; prompt: string; project_id: string | null }>(
    "/problems",
    {
      method: "POST",
      body: JSON.stringify({
        title,
        prompt,
        project_id: projectId ?? null,
      }),
    },
  );
}

export async function createRun(
  problemId: string,
  config: {
    maxGenerations: number;
    populationSize: number;
    survivorCount: number;
    freshAgentCount: number;
    redundancyThreshold: number;
    criticCount: number;
    verificationEnabled: boolean;
  },
) {
  return request<{ id: string; status: RunStatus }>("/runs", {
    method: "POST",
    body: JSON.stringify({
      problem_id: problemId,
      max_generations: config.maxGenerations,
      population_size: config.populationSize,
      survivor_count: config.survivorCount,
      fresh_agent_count: config.freshAgentCount,
      redundancy_threshold: config.redundancyThreshold,
      critic_count: config.criticCount,
      verification_enabled: config.verificationEnabled,
    }),
  });
}

export async function getRun(runId: string) {
  return request<RunDetail>(`/runs/${runId}`, { cache: "no-store" });
}

export async function getRunMetrics(runId: string) {
  return request<RunMetrics>(`/runs/${runId}/metrics`, { cache: "no-store" });
}

export async function getModelStates() {
  return request<ModelState[]>("/model-states", { cache: "no-store" });
}

export async function injectKnowledge(
  runId: string,
  input: { kind: KnowledgeKind; content: string; confidence?: number },
) {
  return request<Knowledge>(`/runs/${runId}/knowledge`, {
    method: "POST",
    body: JSON.stringify({
      kind: input.kind,
      content: input.content,
      confidence: input.confidence ?? null,
    }),
  });
}


export async function createEngineeringRun(input: {
  title: string;
  objective: string;
  projectId?: string;
  maxRepairs: number;
}) {
  return request<EngineeringRun>("/engineering-runs", {
    method: "POST",
    body: JSON.stringify({
      title: input.title,
      objective: input.objective,
      project_id: input.projectId || null,
      max_repairs: input.maxRepairs,
    }),
  });
}

export async function getEngineeringRun(engineeringRunId: string) {
  return request<EngineeringRunDetail>(
    `/engineering-runs/${engineeringRunId}`,
    { cache: "no-store" },
  );
}

export async function listEngineeringRuns() {
  return request<EngineeringRun[]>("/engineering-runs", { cache: "no-store" });
}
