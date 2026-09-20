"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  Agent,
  EngineeringRunDetail,
  Generation,
  KnowledgeKind,
  Lineage,
  ModelState,
  Project,
  RunDetail,
  RunEvent,
  RunMetrics,
  createEngineeringRun,
  createProblem,
  createProject,
  createRun,
  getEngineeringRun,
  getModelStates,
  getRun,
  getRunMetrics,
  injectKnowledge,
  listEngineeringRuns,
  listProjects,
} from "../lib/api";

const EVENT_TYPES = [
  "RUN_CREATED",
  "RUN_STARTED",
  "GENERATION_CREATED",
  "AGENT_SPAWNED",
  "AGENT_STARTED",
  "AGENT_COMPLETED",
  "AGENT_FAILED",
  "JUDGING_STARTED",
  "EVALUATION_COMPLETED",
  "DIVERSITY_ANALYZED",
  "REDUNDANCY_DETECTED",
  "SELECTION_COMPLETED",
  "BRANCH_SELECTED",
  "BRANCH_ELIMINATED",
  "WILDCARD_SELECTED",
  "AGENT_CLONED",
  "FRESH_AGENT_INJECTED",
  "KNOWLEDGE_CREATED",
  "CROSS_POLLINATION_CREATED",
  "CRITIC_STARTED",
  "CRITIC_COMPLETED",
  "CANDIDATE_STATUS_CHANGED",
  "VERIFICATION_STARTED",
  "VERIFICATION_PASSED",
  "VERIFICATION_FAILED",
  "VERIFICATION_INCONCLUSIVE",
  "ROUTING_DECISION",
  "GENERATION_ADVANCED",
  "RUN_COMPLETED",
  "RUN_FAILED",
];

const shortId = (value: string) => value.slice(0, 8);
const pct = (value: number) => Math.round(value * 100);
const humanize = (value: string) => value.replaceAll("_", " ").toLowerCase();

export default function Home() {
  const [projectName, setProjectName] = useState("Research project");
  const [projects, setProjects] = useState<Project[]>([]);
  const [title, setTitle] = useState("Research problem");
  const [prompt, setPrompt] = useState("");
  const [maxGenerations, setMaxGenerations] = useState(3);
  const [populationSize, setPopulationSize] = useState(6);
  const [survivorCount, setSurvivorCount] = useState(3);
  const [freshAgentCount, setFreshAgentCount] = useState(1);
  const [redundancyThreshold, setRedundancyThreshold] = useState(0.78);
  const [criticCount, setCriticCount] = useState(1);
  const [verificationEnabled, setVerificationEnabled] = useState(true);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [metrics, setMetrics] = useState<RunMetrics | null>(null);
  const [models, setModels] = useState<ModelState[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [manualKind, setManualKind] = useState<KnowledgeKind>("HYPOTHESIS");
  const [manualKnowledge, setManualKnowledge] = useState("");
  const [starting, setStarting] = useState(false);
  const [engineeringTitle, setEngineeringTitle] = useState("Engineering task");
  const [engineeringObjective, setEngineeringObjective] = useState("");
  const [engineeringMaxRepairs, setEngineeringMaxRepairs] = useState(2);
  const [engineeringProjectId, setEngineeringProjectId] = useState("");
  const [engineeringRunId, setEngineeringRunId] = useState<string | null>(null);
  const [engineeringRun, setEngineeringRun] = useState<EngineeringRunDetail | null>(null);
  const [engineeringHistoryCount, setEngineeringHistoryCount] = useState(0);
  const [engineeringStarting, setEngineeringStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatic = useCallback(async () => {
    try {
      const [projectList, modelStates, engineeringRuns] = await Promise.all([
        listProjects(),
        getModelStates(),
        listEngineeringRuns(),
      ]);
      setProjects(projectList);
      setModels(modelStates);
      setEngineeringHistoryCount(engineeringRuns.length);
    } catch {
      // The run surface still works if these dashboard calls are temporarily unavailable.
    }
  }, []);

  const refreshRun = useCallback(async (id: string) => {
    try {
      const [detail, runMetrics, modelStates] = await Promise.all([
        getRun(id),
        getRunMetrics(id),
        getModelStates(),
      ]);
      setRun(detail);
      setMetrics(runMetrics);
      setModels(modelStates);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh run.");
    }
  }, []);

  const refreshEngineeringRun = useCallback(async (id: string) => {
    try {
      setEngineeringRun(await getEngineeringRun(id));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not refresh engineering run.",
      );
    }
  }, []);

  useEffect(() => {
    void refreshStatic();
  }, [refreshStatic]);

  useEffect(() => {
    if (!engineeringRunId) return;
    void refreshEngineeringRun(engineeringRunId);
    const timer = window.setInterval(
      () => void refreshEngineeringRun(engineeringRunId),
      1500,
    );
    return () => window.clearInterval(timer);
  }, [engineeringRunId, refreshEngineeringRun]);

  useEffect(() => {
    if (!runId) return;
    void refreshRun(runId);
    const timer = window.setInterval(() => void refreshRun(runId), 2000);
    const source = new EventSource(`${API_BASE_URL}/runs/${runId}/events`);

    const onEvent = (message: MessageEvent<string>) => {
      try {
        const event = JSON.parse(message.data) as RunEvent;
        setEvents((current) =>
          current.some((item) => item.id === event.id)
            ? current
            : [...current, event],
        );
        void refreshRun(runId);
      } catch {
        // Polling remains the fallback if SSE parsing fails.
      }
    };

    for (const eventType of EVENT_TYPES) {
      source.addEventListener(eventType, onEvent as EventListener);
    }
    return () => {
      window.clearInterval(timer);
      source.close();
    };
  }, [refreshRun, runId]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim()) return setError("Enter a research problem first.");
    if (survivorCount >= populationSize) {
      return setError("Survivors must be fewer than the population.");
    }
    if (freshAgentCount >= populationSize) {
      return setError("Fresh explorers must be fewer than the population.");
    }

    setStarting(true);
    setError(null);
    setEvents([]);
    try {
      const project = await createProject(projectName.trim() || "Research project");
      const problem = await createProblem(
        title.trim() || "Research problem",
        prompt.trim(),
        project.id,
      );
      const created = await createRun(problem.id, {
        maxGenerations,
        populationSize,
        survivorCount,
        freshAgentCount,
        redundancyThreshold,
        criticCount,
        verificationEnabled,
      });
      setRunId(created.id);
      await Promise.all([refreshRun(created.id), refreshStatic()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start run.");
    } finally {
      setStarting(false);
    }
  }

  async function startEngineering(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!engineeringObjective.trim()) {
      setError("Enter an engineering objective first.");
      return;
    }
    setEngineeringStarting(true);
    setError(null);
    try {
      const created = await createEngineeringRun({
        title: engineeringTitle.trim() || "Engineering task",
        objective: engineeringObjective.trim(),
        projectId: engineeringProjectId || undefined,
        maxRepairs: engineeringMaxRepairs,
      });
      setEngineeringRunId(created.id);
      await Promise.all([
        refreshEngineeringRun(created.id),
        refreshStatic(),
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not start engineering run.",
      );
    } finally {
      setEngineeringStarting(false);
    }
  }

  async function addKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runId || !manualKnowledge.trim()) return;
    try {
      await injectKnowledge(runId, {
        kind: manualKind,
        content: manualKnowledge.trim(),
      });
      setManualKnowledge("");
      await refreshRun(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not inject knowledge.");
    }
  }

  const generation = run?.generations.at(-1) ?? null;
  const allKnowledge = run?.generations.flatMap((item) => item.knowledge) ?? [];
  const allPackets = run?.generations.flatMap((item) => item.cross_pollination) ?? [];
  const allCandidates = run?.generations.flatMap((item) => item.candidate_states) ?? [];
  const allFindings = run?.generations.flatMap((item) => item.critic_findings) ?? [];
  const allVerifications = run?.generations.flatMap((item) => item.verifications) ?? [];
  const contradictions = allKnowledge.filter((item) => item.kind === "CONTRADICTION");
  const researchers =
    generation?.agents.filter((agent) => agent.role.startsWith("researcher:")) ?? [];
  const judges =
    generation?.agents.filter((agent) => agent.role.startsWith("judge:")) ?? [];
  const critics =
    generation?.agents.filter((agent) => agent.role.startsWith("critic:")) ?? [];
  const lineageByAgent = useMemo(() => {
    const map = new Map<string, Lineage>();
    for (const lineage of generation?.lineages ?? []) {
      map.set(lineage.child_agent_id, lineage);
    }
    return map;
  }, [generation]);

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Agent Coordination</p>
          <h1>Research control room</h1>
          <p className="lede">
            One surface for projects, populations, lineages, knowledge, adversarial
            critique, verification, model routing, budgets, and the complete audit trail.
          </p>
        </div>
        <div className="systemBadge"><span className="pulse" />Phases 0–10</div>
      </header>

      <nav className="controlNav">
        {["overview","population","research","knowledge","candidates","verification","models","engineering","events"].map((item) => (
          <a key={item} href={`#${item}`}>{item}</a>
        ))}
      </nav>

      <section id="overview" className="grid topGrid">
        <form className="panel" onSubmit={start}>
          <div className="panelHeading">
            <div><p className="kicker">Launch</p><h2>New research run</h2></div>
          </div>
          <label>Project<input value={projectName} onChange={(e) => setProjectName(e.target.value)} /></label>
          <label>Problem title<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label>
            Research problem
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={7} />
          </label>
          <div className="configGrid">
            <NumberField label="Generations" value={maxGenerations} min={1} max={20} onChange={setMaxGenerations} />
            <NumberField label="Population" value={populationSize} min={2} max={12} onChange={setPopulationSize} />
            <NumberField label="Survivors" value={survivorCount} min={1} max={11} onChange={setSurvivorCount} />
            <NumberField label="Fresh" value={freshAgentCount} min={0} max={11} onChange={setFreshAgentCount} />
            <NumberField label="Critics" value={criticCount} min={0} max={4} onChange={setCriticCount} />
            <label>
              Redundancy
              <input type="number" min={0} max={1} step={0.01} value={redundancyThreshold}
                onChange={(e) => setRedundancyThreshold(Number(e.target.value))} />
            </label>
          </div>
          <label className="checkRow">
            <input type="checkbox" checked={verificationEnabled}
              onChange={(e) => setVerificationEnabled(e.target.checked)} />
            Verify final candidate
          </label>
          <button type="submit" disabled={starting}>{starting ? "Starting…" : "Start run"}</button>
          {error ? <p className="error">{error}</p> : null}
          <div className="chips">
            {projects.slice(-6).map((project) => <span key={project.id}>{project.name}</span>)}
          </div>
        </form>

        <section className="panel">
          <div className="panelHeading">
            <div><p className="kicker">Overview</p><h2>{run?.problem.title ?? "No active run"}</h2></div>
            {run ? <span className={`status status-${run.status}`}>{run.status}</span> : null}
          </div>
          {run ? (
            <>
              <p className="problemText">{run.problem.prompt}</p>
              <div className="metricGrid">
                <Metric label="Generation" value={(generation?.index ?? 0) + 1} suffix={`/${run.max_generations}`} />
                <Metric label="Model calls" value={metrics?.model_calls ?? 0} />
                <Metric label="Knowledge" value={metrics?.knowledge_items ?? 0} />
                <Metric label="Verifications" value={metrics?.verifications ?? 0} />
                <Metric label="Verified" value={metrics?.verified_candidates ?? 0} />
                <Metric label="Niches" value={metrics?.active_niches ?? 0} />
              </div>
              <div className="chips">
                <span>{metrics?.input_tokens ?? 0} input tok</span>
                <span>{metrics?.output_tokens ?? 0} output tok</span>
                <span>€{(metrics?.estimated_cost ?? 0).toFixed(4)} est.</span>
                <span>judge Δ {(metrics?.judge_disagreement ?? 0).toFixed(3)}</span>
              </div>
              <p className="runId">Run <code>{run.id}</code></p>
            </>
          ) : <div className="emptyState">Start a run to populate the control room.</div>}
        </section>
      </section>

      {run && generation ? (
        <>
          <section id="population" className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Population</p><h2>Generation {generation.index + 1}</h2></div>
              <span className="count">{generation.agents.length}</span>
            </div>
            <div className="tripleGrid">
              <AgentPanel title="Researchers" agents={researchers} lineageByAgent={lineageByAgent} />
              <AgentPanel title="Blind judges" agents={judges} lineageByAgent={new Map()} />
              <AgentPanel title="Critics" agents={critics} lineageByAgent={new Map()} />
            </div>
          </section>

          <section id="research" className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Research</p><h2>Submissions, selection & transfer</h2></div>
              <span className="count">{generation.submissions.length}</span>
            </div>
            <div className="submissionGrid">
              {generation.submissions.map((submission) => (
                <article className="card" key={submission.id}>
                  <div className="cardTopline"><span>{shortId(submission.id)}</span><code>{shortId(submission.agent_id)}</code></div>
                  <h3>{submission.summary}</h3>
                  <p>{submission.approach}</p>
                  <div className="chips">
                    <span>{submission.claims.length} claims</span>
                    <span>{submission.discoveries.length} discoveries</span>
                    <span>{submission.failed_attempts.length} failed</span>
                  </div>
                </article>
              ))}
            </div>
            <div className="evolutionGrid">
              {run.generations.map((item) => <GenerationHistory key={item.id} generation={item} />)}
            </div>
            <div className="stack compactStack">
              {allPackets.map((packet) => (
                <article className="agentRow" key={packet.id}>
                  <div><strong>{humanize(packet.kind)}</strong><code>{shortId(packet.source_submission_id)} → {shortId(packet.target_agent_id)}</code></div>
                </article>
              ))}
            </div>
          </section>

          <section id="knowledge" className="grid halfGrid">
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Knowledge</p><h2>Durable research memory</h2></div>
                <span className="count">{allKnowledge.length}</span>
              </div>
              <form onSubmit={addKnowledge} className="manualForm">
                <select value={manualKind} onChange={(e) => setManualKind(e.target.value as KnowledgeKind)}>
                  {["HYPOTHESIS","CANDIDATE_LEMMA","COUNTEREXAMPLE","CONTRADICTION","PROMISING_APPROACH","UNRESOLVED_QUESTION"].map((kind) => (
                    <option key={kind} value={kind}>{humanize(kind)}</option>
                  ))}
                </select>
                <input value={manualKnowledge} onChange={(e) => setManualKnowledge(e.target.value)}
                  placeholder="Inject a durable research note…" />
                <button type="submit">Inject</button>
              </form>
              <div className="stack scrollStack">
                {[...allKnowledge].reverse().slice(0, 30).map((item) => (
                  <article className="card" key={item.id}>
                    <div className="cardTopline"><span>{humanize(item.kind)}</span><span>{humanize(item.status)}</span></div>
                    <p>{item.content}</p>
                  </article>
                ))}
              </div>
            </section>
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Contradictions</p><h2>Conflict watch</h2></div>
                <span className="count">{contradictions.length}</span>
              </div>
              {contradictions.length ? contradictions.map((item) => (
                <article className="card" key={item.id}><p>{item.content}</p></article>
              )) : <p className="muted">No explicit contradictions recorded yet.</p>}
            </section>
          </section>

          <section id="candidates" className="grid halfGrid">
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Candidates</p><h2>Lifecycle</h2></div>
                <span className="count">{allCandidates.length}</span>
              </div>
              <div className="stack">
                {allCandidates.map((state) => (
                  <article className="agentRow" key={state.id}>
                    <div><strong>{shortId(state.submission_id)}</strong><code>{state.id}</code></div>
                    <span className={`status status-${state.status}`}>{state.status}</span>
                  </article>
                ))}
              </div>
            </section>
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Adversarial review</p><h2>Critic findings</h2></div>
                <span className="count">{allFindings.length}</span>
              </div>
              <div className="stack">
                {allFindings.map((finding) => (
                  <article className="card" key={finding.id}>
                    <div className="cardTopline">
                      <span>{finding.fatal_error ? "fatal" : "survived"}</span>
                      <span>{pct(finding.confidence)}% confidence</span>
                    </div>
                    <p>{finding.critique}</p>
                    {finding.counterexample ? <div className="answer"><span>Counterexample</span><p>{finding.counterexample}</p></div> : null}
                  </article>
                ))}
              </div>
            </section>
          </section>

          <section id="verification" className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Verification</p><h2>Deterministic checks</h2></div>
              <span className="count">{allVerifications.length}</span>
            </div>
            <div className="tripleGrid">
              {allVerifications.map((result) => (
                <article className="card" key={result.id}>
                  <div className="cardTopline"><span>{humanize(result.kind)}</span><span>{result.status}</span></div>
                  <p>{result.detail}</p>
                </article>
              ))}
            </div>
          </section>

          <section id="models" className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Models & budgets</p><h2>Adaptive routing state</h2></div>
              <span className="count">{models.length}</span>
            </div>
            <div className="modelGrid">
              {models.map((model) => <ModelCard key={model.id} model={model} />)}
            </div>
          </section>

          <section id="engineering" className="grid topGrid">
            <form className="panel" onSubmit={startEngineering}>
              <div className="panelHeading">
                <div>
                  <p className="kicker">Engineering factory</p>
                  <h2>Planner → implementation → tests → review → repair</h2>
                </div>
                <span className="count">{engineeringHistoryCount} runs</span>
              </div>
              <label>
                Task title
                <input
                  value={engineeringTitle}
                  onChange={(e) => setEngineeringTitle(e.target.value)}
                  maxLength={300}
                />
              </label>
              <label>
                Objective
                <textarea
                  value={engineeringObjective}
                  onChange={(e) => setEngineeringObjective(e.target.value)}
                  placeholder="Describe the software change or application to build..."
                  rows={6}
                />
              </label>
              <div className="engineeringConfig">
                <label>
                  Project
                  <select
                    value={engineeringProjectId}
                    onChange={(e) => setEngineeringProjectId(e.target.value)}
                  >
                    <option value="">No project</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </label>
                <NumberField
                  label="Max repairs"
                  value={engineeringMaxRepairs}
                  min={0}
                  max={5}
                  onChange={setEngineeringMaxRepairs}
                />
              </div>
              <button type="submit" disabled={engineeringStarting}>
                {engineeringStarting ? "Starting…" : "Start engineering run"}
              </button>
            </form>

            <section className="panel">
              <div className="panelHeading">
                <div>
                  <p className="kicker">Factory state</p>
                  <h2>{engineeringRun?.title ?? "No active engineering run"}</h2>
                </div>
                {engineeringRun ? (
                  <span className={`status status-${engineeringRun.status}`}>
                    {engineeringRun.status}
                  </span>
                ) : null}
              </div>
              {engineeringRun ? (
                <>
                  <p className="problemText">{engineeringRun.objective}</p>
                  <div className="metricGrid">
                    <Metric label="Repair cycle" value={engineeringRun.repair_count} />
                    <Metric label="Max repairs" value={engineeringRun.max_repairs} />
                    <Metric label="Artifacts" value={engineeringRun.artifacts.length} />
                    <Metric label="Checks" value={engineeringRun.checks.length} />
                    <Metric
                      label="Passed"
                      value={engineeringRun.checks.filter((check) => check.passed).length}
                    />
                    <Metric
                      label="Failed"
                      value={engineeringRun.checks.filter((check) => !check.passed).length}
                    />
                  </div>
                  <div className="engineeringStages">
                    {engineeringRun.artifacts.map((artifact) => (
                      <article className="card" key={artifact.id}>
                        <div className="cardTopline">
                          <span>{humanize(artifact.stage)}</span>
                          <span>cycle {artifact.repair_cycle}</span>
                        </div>
                        <h3>{humanize(artifact.role)}</h3>
                        <pre>{JSON.stringify(artifact.content, null, 2)}</pre>
                      </article>
                    ))}
                  </div>
                  <div className="stack compactStack">
                    {engineeringRun.checks.map((check) => (
                      <article className="agentRow" key={check.id}>
                        <div>
                          <strong>{humanize(check.name)}</strong>
                          <span className="lineageLabel">
                            cycle {check.repair_cycle} · {check.detail}
                          </span>
                        </div>
                        <span
                          className={check.passed ? "status status-COMPLETED" : "status status-FAILED"}
                        >
                          {check.passed ? "PASS" : "FAIL"}
                        </span>
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="emptyState">
                  Engineering runs use the same durable queue, adaptive routing, and model accounting.
                </div>
              )}
            </section>
          </section>

          <section id="events" className="grid halfGrid">
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Scoring</p><h2>Current evaluations</h2></div>
                <span className="count">{generation.evaluations.length}</span>
              </div>
              <div className="stack">
                {generation.evaluations.map((evaluation) => (
                  <article className="card" key={evaluation.id}>
                    <div className="cardTopline"><span>{shortId(evaluation.submission_id)}</span><span>{evaluation.fatal_error ? "fatal" : "clean"}</span></div>
                    <div className="scoreGrid">
                      <Score label="Correct" value={evaluation.correctness} />
                      <Score label="Rigor" value={evaluation.rigor} />
                      <Score label="Novelty" value={evaluation.novelty} />
                      <Score label="Progress" value={evaluation.research_progress} />
                      <Score label="Verify" value={evaluation.verifiability} />
                      <Score label="Confidence" value={evaluation.judge_confidence} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section className="panel timelinePanel">
              <div className="panelHeading">
                <div><p className="kicker">Audit trail</p><h2>Run events</h2></div>
                <span className="count">{events.length}</span>
              </div>
              <div className="timeline">
                {[...events].reverse().map((event) => (
                  <article className="timelineItem" key={event.id}>
                    <span className="eventDot" />
                    <div><strong>{event.type.replaceAll("_", " ")}</strong><span>{event.created_at ? new Date(event.created_at).toLocaleTimeString() : "now"}</span></div>
                  </article>
                ))}
              </div>
            </section>
          </section>
        </>
      ) : null}
    </main>
  );
}

function NumberField({ label, value, min, max, onChange }: {
  label: string; value: number; min: number; max: number; onChange: (value: number) => void;
}) {
  return <label>{label}<input type="number" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>;
}

function Metric({ label, value, suffix = "" }: { label: string; value: number; suffix?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}{suffix}</strong></div>;
}

function Score({ label, value }: { label: string; value: number }) {
  return <span>{label}<strong>{pct(value)}</strong></span>;
}

function AgentPanel({ title, agents, lineageByAgent }: {
  title: string; agents: Agent[]; lineageByAgent: Map<string, Lineage>;
}) {
  return (
    <section>
      <h3 className="subhead">{title}</h3>
      <div className="stack">
        {agents.map((agent) => {
          const lineage = lineageByAgent.get(agent.id);
          return (
            <article className="agentRow" key={agent.id}>
              <div>
                <strong>{agent.role}</strong>
                <code>{shortId(agent.id)}</code>
                <span className="lineageLabel">{humanize(agent.niche)} · {humanize(agent.origin)}</span>
                {lineage ? <span className="lineageLabel">{humanize(lineage.mutation_type)} ← {shortId(lineage.parent_submission_id)}</span> : null}
              </div>
              <span className={`status status-${agent.status}`}>{agent.status}</span>
            </article>
          );
        })}
        {!agents.length ? <p className="muted">None yet.</p> : null}
      </div>
    </section>
  );
}

function GenerationHistory({ generation }: { generation: Generation }) {
  return (
    <article className="generationHistory">
      <div className="cardTopline"><strong>G{generation.index + 1}</strong><span>{generation.submissions.length} submissions</span></div>
      <div className="selectionList">
        {generation.selections.map((decision) => (
          <span key={decision.id}
            className={decision.selected ? "selection selected" : "selection eliminated"}
            title={decision.reason}>
            #{decision.rank} {humanize(decision.selection_kind)} · n{pct(decision.novelty_score)}
          </span>
        ))}
      </div>
      <div className="chips">
        {generation.lineages.map((lineage) => (
          <span key={lineage.id}>{humanize(lineage.mutation_type)} ← {shortId(lineage.parent_submission_id)}</span>
        ))}
      </div>
    </article>
  );
}

function ModelCard({ model }: { model: ModelState }) {
  return (
    <article className="card">
      <div className="cardTopline"><span>{model.enabled ? "enabled" : "disabled"}</span><code>{shortId(model.model_profile_id)}</code></div>
      <div className="scoreGrid">
        <Score label="Reliability" value={1 - model.failure_rate} />
        <Score label="Rate pressure" value={model.rate_limit_pressure} />
        <Score label="Scarcity" value={model.scarcity} />
      </div>
      <div className="chips">
        <span>{Math.round(model.latency_ms)}ms</span>
        <span>{model.available_concurrency} concurrency</span>
        <span>cash {model.marginal_cash_cost.toFixed(3)}</span>
        <span>credit {model.credit_cost.toFixed(3)}</span>
      </div>
    </article>
  );
}
