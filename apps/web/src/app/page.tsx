"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  Agent,
  Generation,
  Lineage,
  RunDetail,
  RunEvent,
  createProblem,
  createRun,
  getRun,
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
  "SELECTION_COMPLETED",
  "BRANCH_SELECTED",
  "BRANCH_ELIMINATED",
  "AGENT_CLONED",
  "GENERATION_ADVANCED",
  "RUN_COMPLETED",
  "RUN_FAILED",
];

const shortId = (value: string) => value.slice(0, 8);
const pct = (value: number) => Math.round(value * 100);

export default function Home() {
  const [title, setTitle] = useState("Research problem");
  const [prompt, setPrompt] = useState("");
  const [maxGenerations, setMaxGenerations] = useState(3);
  const [populationSize, setPopulationSize] = useState(4);
  const [survivorCount, setSurvivorCount] = useState(2);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshRun = useCallback(async (id: string) => {
    try {
      setRun(await getRun(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh run.");
    }
  }, []);

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
        // Polling remains the fallback if a malformed event arrives.
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
    if (!prompt.trim()) {
      setError("Enter a research problem first.");
      return;
    }
    if (survivorCount >= populationSize) {
      setError("Survivors must be fewer than the population.");
      return;
    }

    setStarting(true);
    setError(null);
    setRun(null);
    setEvents([]);

    try {
      const problem = await createProblem(
        title.trim() || "Research problem",
        prompt.trim(),
      );
      const created = await createRun(problem.id, {
        maxGenerations,
        populationSize,
        survivorCount,
      });
      setRunId(created.id);
      await refreshRun(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start run.");
    } finally {
      setStarting(false);
    }
  }

  const generation = run?.generations.at(-1) ?? null;
  const researchers = generation?.agents.filter((a) => a.role.startsWith("researcher:")) ?? [];
  const judges = generation?.agents.filter((a) => a.role.startsWith("judge:")) ?? [];
  const lineageByAgent = useMemo(() => {
    const map = new Map<string, Lineage>();
    for (const lineage of generation?.lineages ?? []) {
      map.set(lineage.child_agent_id, lineage);
    }
    return map;
  }, [generation]);

  const counts = useMemo(() => {
    const agents = generation?.agents ?? [];
    return {
      total: agents.length,
      running: agents.filter((a) => a.status === "RUNNING").length,
      complete: agents.filter((a) => a.status === "COMPLETED").length,
      failed: agents.filter((a) => a.status === "FAILED").length,
    };
  }, [generation]);

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Agent Coordination</p>
          <h1>Research tournament</h1>
          <p className="lede">
            Launch an evolutionary research run, watch independent agents compete,
            then follow selection, cloning, mutation, and lineage across generations.
          </p>
        </div>
        <div className="systemBadge"><span className="pulse" />Phase 2</div>
      </header>

      <section className="grid topGrid">
        <form className="panel" onSubmit={start}>
          <div className="panelHeading">
            <div><p className="kicker">New tournament</p><h2>Research problem</h2></div>
          </div>

          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} />
          </label>

          <label>
            Problem
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the research problem..."
              rows={8}
            />
          </label>

          <div className="configGrid">
            <label>
              Generations
              <input
                type="number"
                min={1}
                max={20}
                value={maxGenerations}
                onChange={(e) => setMaxGenerations(Number(e.target.value))}
              />
            </label>
            <label>
              Population
              <input
                type="number"
                min={2}
                max={12}
                value={populationSize}
                onChange={(e) => setPopulationSize(Number(e.target.value))}
              />
            </label>
            <label>
              Survivors
              <input
                type="number"
                min={1}
                max={11}
                value={survivorCount}
                onChange={(e) => setSurvivorCount(Number(e.target.value))}
              />
            </label>
          </div>

          <button type="submit" disabled={starting}>
            {starting ? "Starting…" : "Start tournament"}
          </button>
          {error ? <p className="error">{error}</p> : null}
        </form>

        <section className="panel">
          <div className="panelHeading">
            <div>
              <p className="kicker">Live state</p>
              <h2>{run ? run.problem.title : "No active run"}</h2>
            </div>
            {run ? <span className={`status status-${run.status}`}>{run.status}</span> : null}
          </div>

          {run ? (
            <>
              <p className="problemText">{run.problem.prompt}</p>
              <div className="metricGrid">
                <Metric label="Generation" value={(generation?.index ?? 0) + 1} suffix={`/${run.max_generations}`} />
                <Metric label="Population" value={run.population_size} />
                <Metric label="Survivors" value={run.survivor_count} />
                <Metric label="Running" value={counts.running} />
                <Metric label="Submissions" value={generation?.submissions.length ?? 0} />
                <Metric label="Evaluations" value={generation?.evaluations.length ?? 0} />
              </div>
              <p className="runId">Run <code>{run.id}</code></p>
            </>
          ) : (
            <div className="emptyState">
              <div>
                <p>A tournament will appear here when started.</p>
                <span>research → judge → select → clone + mutate → next generation</span>
              </div>
            </div>
          )}
        </section>
      </section>

      {run && generation ? (
        <>
          <section className="panel generationStrip">
            <div>
              <p className="kicker">Tournament progress</p>
              <h2>Generations</h2>
            </div>
            <div className="generationPills">
              {run.generations.map((item) => (
                <span
                  key={item.id}
                  className={item.id === generation.id ? "generationPill active" : "generationPill"}
                >
                  G{item.index + 1}
                  <small>{item.submissions.length}/{run.population_size}</small>
                </span>
              ))}
            </div>
          </section>

          <section className="grid halfGrid">
            <AgentPanel
              title="Researchers"
              kicker={`Generation ${generation.index + 1}`}
              agents={researchers}
              lineageByAgent={lineageByAgent}
              empty="Researchers spawn when the generation starts."
            />
            <AgentPanel
              title="Blind judges"
              kicker="Evaluation"
              agents={judges}
              lineageByAgent={new Map()}
              empty="Judges spawn after all research branches finish."
            />
          </section>

          <section className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Research artifacts</p><h2>Current submissions</h2></div>
              <span className="count">{generation.submissions.length}</span>
            </div>
            {generation.submissions.length ? (
              <div className="submissionGrid">
                {generation.submissions.map((submission, index) => (
                  <article className="card" key={submission.id}>
                    <div className="cardTopline">
                      <span>Candidate {index + 1}</span>
                      <code>{shortId(submission.agent_id)}</code>
                    </div>
                    <h3>{submission.summary}</h3>
                    <p>{submission.approach}</p>
                    {submission.final_answer ? (
                      <div className="answer">
                        <span>Final candidate</span>
                        <p>{submission.final_answer}</p>
                      </div>
                    ) : null}
                    <div className="chips">
                      <span>{submission.claims.length} claims</span>
                      <span>{submission.discoveries.length} discoveries</span>
                      <span>{submission.open_questions.length} open questions</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : <p className="muted">Structured submissions appear as researchers finish.</p>}
          </section>

          <section className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Evolution</p><h2>Selection & lineage history</h2></div>
              <span className="count">{run.generations.length}</span>
            </div>
            <div className="evolutionGrid">
              {run.generations.map((item) => (
                <GenerationHistory key={item.id} generation={item} />
              ))}
            </div>
          </section>

          <section className="grid halfGrid">
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Scoring</p><h2>Current evaluations</h2></div>
                <span className="count">{generation.evaluations.length}</span>
              </div>
              <div className="stack">
                {generation.evaluations.length ? generation.evaluations.map((evaluation) => (
                  <article className="card" key={evaluation.id}>
                    <div className="cardTopline">
                      <span>Submission {shortId(evaluation.submission_id)}</span>
                      <span>{evaluation.fatal_error ? "Fatal error" : "No fatal error"}</span>
                    </div>
                    <div className="scoreGrid">
                      <Score label="Correct" value={evaluation.correctness} />
                      <Score label="Rigor" value={evaluation.rigor} />
                      <Score label="Novelty" value={evaluation.novelty} />
                      <Score label="Progress" value={evaluation.research_progress} />
                      <Score label="Verifiable" value={evaluation.verifiability} />
                      <Score label="Confidence" value={evaluation.judge_confidence} />
                    </div>
                    <p>{evaluation.critique}</p>
                  </article>
                )) : <p className="muted">Blind evaluations appear during judging.</p>}
              </div>
            </section>

            <section className="panel timelinePanel">
              <div className="panelHeading">
                <div><p className="kicker">Audit trail</p><h2>Run events</h2></div>
                <span className="count">{events.length}</span>
              </div>
              <div className="timeline">
                {events.length ? [...events].reverse().map((event) => (
                  <article className="timelineItem" key={event.id}>
                    <span className="eventDot" />
                    <div>
                      <strong>{event.type.replaceAll("_", " ")}</strong>
                      <span>
                        {event.created_at ? new Date(event.created_at).toLocaleTimeString() : "now"}
                      </span>
                    </div>
                  </article>
                )) : <p className="muted">Waiting for run events…</p>}
              </div>
            </section>
          </section>
        </>
      ) : null}
    </main>
  );
}

function Metric({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: number;
  suffix?: string;
}) {
  return <div className="metric"><span>{label}</span><strong>{value}{suffix}</strong></div>;
}

function Score({ label, value }: { label: string; value: number }) {
  return <span>{label}<strong>{pct(value)}</strong></span>;
}

function AgentPanel({
  title,
  kicker,
  agents,
  lineageByAgent,
  empty,
}: {
  title: string;
  kicker: string;
  agents: Agent[];
  lineageByAgent: Map<string, Lineage>;
  empty: string;
}) {
  return (
    <section className="panel">
      <div className="panelHeading">
        <div><p className="kicker">{kicker}</p><h2>{title}</h2></div>
        <span className="count">{agents.length}</span>
      </div>
      {agents.length ? (
        <div className="stack">
          {agents.map((agent) => {
            const lineage = lineageByAgent.get(agent.id);
            return (
              <article className="agentRow" key={agent.id}>
                <div>
                  <strong>{agent.role}</strong>
                  <code>{shortId(agent.id)}</code>
                  {lineage ? (
                    <span className="lineageLabel">
                      {lineage.mutation_type.toLowerCase()} from {shortId(lineage.parent_submission_id)}
                    </span>
                  ) : null}
                </div>
                <span className={`status status-${agent.status}`}>{agent.status}</span>
              </article>
            );
          })}
        </div>
      ) : <p className="muted">{empty}</p>}
    </section>
  );
}

function GenerationHistory({ generation }: { generation: Generation }) {
  const selected = generation.selections.filter((item) => item.selected);
  const eliminated = generation.selections.filter((item) => !item.selected);

  return (
    <article className="generationHistory">
      <div className="cardTopline">
        <strong>Generation {generation.index + 1}</strong>
        <span>{generation.submissions.length} submissions</span>
      </div>
      {generation.selections.length ? (
        <>
          <p>
            <b>{selected.length}</b> selected · <b>{eliminated.length}</b> eliminated
          </p>
          <div className="selectionList">
            {generation.selections.map((decision) => (
              <span
                key={decision.id}
                className={decision.selected ? "selection selected" : "selection eliminated"}
              >
                #{decision.rank} {shortId(decision.submission_id)}
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className="muted">Selection pending or final generation.</p>
      )}
      {generation.lineages.length ? (
        <div className="chips">
          {generation.lineages.map((lineage) => (
            <span key={lineage.id}>
              {lineage.mutation_type.toLowerCase()} ← {shortId(lineage.parent_submission_id)}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}
