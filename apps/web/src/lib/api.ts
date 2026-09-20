export type RunStatus =
  | "CREATED"
  | "RESEARCHING"
  | "JUDGING"
  | "COMPLETED"
  | "PAUSED"
  | "FAILED";

export type AgentStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export type MutationType =
  | "STRENGTHEN"
  | "FALSIFY"
  | "REDERIVE"
  | "GENERALIZE";

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
};

export type Lineage = {
  id: string;
  child_agent_id: string;
  parent_submission_id: string;
  mutation_type: MutationType;
};

export type Agent = {
  id: string;
  role: string;
  status: AgentStatus;
};

export type Generation = {
  id: string;
  index: number;
  agents: Agent[];
  submissions: Submission[];
  evaluations: Evaluation[];
  selections: SelectionDecision[];
  lineages: Lineage[];
};

export type RunDetail = {
  id: string;
  status: RunStatus;
  max_generations: number;
  population_size: number;
  survivor_count: number;
  problem: {
    id: string;
    title: string;
    prompt: string;
  };
  generations: Generation[];
};

export type RunEvent = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
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

export async function createProblem(title: string, prompt: string) {
  return request<{ id: string; title: string; prompt: string }>("/problems", {
    method: "POST",
    body: JSON.stringify({ title, prompt }),
  });
}

export async function createRun(
  problemId: string,
  config: {
    maxGenerations: number;
    populationSize: number;
    survivorCount: number;
  },
) {
  return request<{
    id: string;
    problem_id: string;
    status: RunStatus;
    max_generations: number;
    population_size: number;
    survivor_count: number;
  }>("/runs", {
    method: "POST",
    body: JSON.stringify({
      problem_id: problemId,
      max_generations: config.maxGenerations,
      population_size: config.populationSize,
      survivor_count: config.survivorCount,
    }),
  });
}

export async function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`, { cache: "no-store" });
}
