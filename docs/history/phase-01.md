# Phase 1 — Baseline Vertical Slice

## Purpose

Prove the full orchestration loop before building evolutionary research features.

## User-visible behavior

A user can enter a research problem and start a run.

The system:

1. creates Generation 0,
2. launches four independent researchers,
3. stores four structured submissions,
4. anonymizes and shuffles them for judging,
5. launches two independent judges,
6. stores multidimensional evaluations,
7. aggregates the results,
8. marks the run complete,
9. exposes the full run history in the UI.

## Hard exclusions

Do not add yet:

- cloning
- mutation
- elimination
- cross-pollination
- lineage trees
- persistent research memory
- knowledge graphs
- vector databases
- formal verification
- dynamic population sizing
- complex routing optimization
- Redis/Celery/Temporal/Kafka
- production-grade dashboards

## Required domain types

- Problem
- Run
- Generation
- Agent
- Submission
- Evaluation
- ModelProfile
- ModelCall
- Job
- RunEvent

## Required provider behavior

Implement FakeProvider first.

FakeProvider must support deterministic scripted researcher and judge responses so integration tests can run with no network access.

After the baseline passes, connect one real automated provider.

## Required API surface

Minimum useful endpoints:

```text
POST /problems
POST /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/events
```

Additional endpoints may be added only where the UI actually needs them.

## Required worker jobs

At minimum:

- create_generation
- run_research_agent
- start_judging
- run_judge
- finalize_run

Each job must be idempotent.

## Persistence rules

- PostgreSQL is authoritative.
- All state changes happen transactionally.
- Worker claims must be concurrency-safe.
- Model calls are logged even when they fail.
- Raw model output is retained.
- Structured parse failures are explicit events/errors, never silently discarded.

## Judging rules

- Judges must not see model/provider identity.
- Submission ordering must be randomized.
- Each judge evaluates independently.
- Evaluation dimensions are stored separately.
- A fatal-error flag is preserved independently from average scores.

## Minimal UI

The first UI only needs:

- new problem/run form
- run status
- researcher list/status
- submission inspection
- judge evaluations
- event timeline

No visual tournament graph is required yet.

## Acceptance tests

### Unit

- state-machine transition validation
- job idempotency
- evaluation aggregation
- provider contract
- structured-output validation

### Integration

A single test must prove:

```text
Problem created
Run created
Generation 0 created
4 researcher jobs execute
4 submissions stored
2 judge jobs execute
evaluations stored
Run reaches COMPLETED
event log contains expected lifecycle
```

### Failure-path integration

At least:

- one researcher fails and retries
- one malformed structured output is handled
- one judge fails and retries
- duplicate job execution does not duplicate durable state

## Definition of done

Phase 1 is done when the FakeProvider baseline is reliable, observable, and reproducible, and one real provider can be swapped in without changing core orchestration code.
