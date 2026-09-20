"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
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
  "RUN_COMPLETED",
  "RUN_FAILED",
];

const shortId = (value: string) => value.slice(0, 8);
const pct = (value: number) => Math.round(value * 100);

export default function Home() {
  const [title, setTitle] = useState("Research problem");
  const [prompt, setPrompt] = useState("");
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

    setStarting(true);
    setError(null);
    setRun(null);
    setEvents([]);

    try {
      const problem = await createProblem(title.trim() || "Research problem", prompt.trim());
      const created = await createRun(problem.id);
      setRunId(created.id);
      await refreshRun(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start run.");
    } finally {
      setStarting(false);
    }
  }

  const generation = run?.generations[0] ?? null;
  const researchers = generation?.agents.filter((a) => a.role.startsWith("researcher:")) ?? [];
  const judges = generation?.agents.filter((a) => a.role.startsWith("judge:")) ?? [];
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
          <h1>Research control room</h1>
          <p className="lede">
            Launch a run, watch independent researchers execute, and inspect
            structured submissions, blind judging, and the audit trail.
          </p>
        </div>
        <div className="systemBadge"><span className="pulse" />Phase 1</div>
      </header>

      <section className="grid topGrid">
        <form className="panel" onSubmit={start}>
          <div className="panelHeading">
            <div><p className="kicker">New run</p><h2>Research problem</h2></div>
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
              rows={9}
            />
          </label>
          <button type="submit" disabled={starting}>
            {starting ? "Starting…" : "Start research run"}
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
                <Metric label="Agents" value={counts.total} />
                <Metric label="Running" value={counts.running} />
                <Metric label="Complete" value={counts.complete} />
                <Metric label="Submissions" value={generation?.submissions.length ?? 0} />
                <Metric label="Evaluations" value={generation?.evaluations.length ?? 0} />
                <Metric label="Failures" value={counts.failed} />
              </div>
              <p className="runId">Run <code>{run.id}</code></p>
            </>
          ) : (
            <div className="emptyState">
              <div>
                <p>A run will appear here when started.</p>
                <span>4 researchers → 2 blind judges → completed run</span>
              </div>
            </div>
          )}
        </section>
      </section>

      {run ? (
        <>
          <section className="grid halfGrid">
            <AgentPanel title="Researchers" kicker="Population" agents={researchers} empty="Researchers spawn when the run starts." />
            <AgentPanel title="Blind judges" kicker="Evaluation" agents={judges} empty="Judges spawn after research completes." />
          </section>

          <section className="panel">
            <div className="panelHeading">
              <div><p className="kicker">Research artifacts</p><h2>Submissions</h2></div>
              <span className="count">{generation?.submissions.length ?? 0}</span>
            </div>
            {generation?.submissions.length ? (
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

          <section className="grid halfGrid">
            <section className="panel">
              <div className="panelHeading">
                <div><p className="kicker">Scoring</p><h2>Evaluations</h2></div>
                <span className="count">{generation?.evaluations.length ?? 0}</span>
              </div>
              <div className="stack">
                {generation?.evaluations.length ? generation.evaluations.map((evaluation) => (
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

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function Score({ label, value }: { label: string; value: number }) {
  return <span>{label}<strong>{pct(value)}</strong></span>;
}

function AgentPanel({
  title,
  kicker,
  agents,
  empty,
}: {
  title: string;
  kicker: string;
  agents: { id: string; role: string; status: string }[];
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
          {agents.map((agent) => (
            <article className="agentRow" key={agent.id}>
              <div><strong>{agent.role}</strong><code>{shortId(agent.id)}</code></div>
              <span className={`status status-${agent.status}`}>{agent.status}</span>
            </article>
          ))}
        </div>
      ) : <p className="muted">{empty}</p>}
    </section>
  );
}
