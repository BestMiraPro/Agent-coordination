# Architecture

## Goal

Build a modular, research-oriented multi-agent system that can explore uncertain solution spaces while keeping orchestration deterministic, model providers replaceable, and all important state durable and auditable.

## Architectural shape

Use a modular monolith first.

```text
Browser
  |
  v
Next.js control room
  |
  v
FastAPI API
  |----------------------> PostgreSQL
  |                           |
  |                           +--> durable jobs
  |                           +--> runs / agents / submissions
  |                           +--> evaluations / model calls
  |                           +--> append-only run events
  |
  +----------------------> Python worker
                                |
                                v
                         Deterministic orchestrator
                                |
                                v
                          Model scheduler
                           /     |      \
                        Muse   W&B-*   future providers
```

Do not start with Redis, Celery, Kafka, Temporal, Kubernetes, microservices, or a vector database. Add infrastructure only after measurement shows the need.

## Dependency direction

```text
API / worker / web
        |
        v
infrastructure / providers
        |
        v
       core
```

`packages/core` must not depend on FastAPI, SQLAlchemy, Next.js, a concrete model vendor, or a concrete queue implementation.

## Core invariants

1. LLMs do research; code owns orchestration state.
2. Agents are disposable; useful artifacts are durable.
3. Every model call is attributable, measurable, and retry-safe.
4. Provider-specific logic does not leak into the core domain.
5. Agents see only context explicitly supplied to them.
6. Structured outputs are preferred; raw outputs are always retained.
7. PostgreSQL is the canonical state store.
8. Jobs are idempotent and safe to retry.
9. Judges do not see model identity.
10. The runtime does not depend on ChatGPT GPT-5.6 Sol or Astra being callable.
11. Convergence is not treated as proof of correctness.
12. External/deterministic verification outranks model confidence.

## Initial repository layout

```text
Agent-coordination/
├── apps/
│   └── web/
├── services/
│   ├── api/
│   └── worker/
├── packages/
│   ├── core/
│   │   ├── domain/
│   │   ├── orchestration/
│   │   ├── scheduling/
│   │   ├── evaluation/
│   │   └── events/
│   ├── providers/
│   ├── persistence/
│   └── prompts/
├── config/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── provider_contracts/
│   └── evals/
├── docs/
│   └── adr/
├── docker-compose.yml
├── pyproject.toml
├── pnpm-workspace.yaml
├── Makefile
└── .env.example
```

## Core entities

The initial domain model is intentionally small:

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

Do not add KnowledgeItem, Claim, Lineage, Verification, or CrossPollinationPacket until the baseline is working.

## Structured submission model

Each researcher stores both a structured representation and the original raw text.

Recommended logical fields:

```text
Submission
- id
- agent_id
- summary
- approach
- claims[]
- evidence[]
- discoveries[]
- failed_attempts[]
- open_questions[]
- final_answer?
- raw_response
```

The orchestrator should operate primarily on structured state.

## Evaluation model

Do not reduce quality to a single score.

```text
Evaluation
- correctness
- rigor
- novelty
- research_progress
- verifiability
- fatal_error
- judge_confidence
- critique
```

A UI score can exist later, but selection policy must retain multidimensional information.

## Initial run state machine

```text
CREATED
  |
  v
RESEARCHING
  |
  v
JUDGING
  |
  v
COMPLETED

Any stage -> PAUSED
Any stage -> FAILED
```

State transitions are deterministic code paths, never free-form LLM decisions.

## Provider abstraction

The core should target a single provider-neutral interface.

```python
class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...
```

The orchestration layer asks the scheduler to execute a task. It never calls provider-specific methods directly.

Every model call records at least:

- provider
- model
- task type
- latency
- input/output token counts when available
- estimated cost or credit usage
- retry count
- status
- raw provider metadata

## Scheduler

Start with a simple policy engine. Model selection may consider:

- capability match
- current availability
- rate-limit pressure
- recent reliability
- latency
- W&B credit consumption
- task-specific benchmark quality

A later routing objective may approximate:

```text
utility = expected_success * task_value
          ---------------------------------
          weighted(cost, latency, scarcity)
```

Do not over-engineer this in Phase 1.

## Persistence and jobs

PostgreSQL is the single source of truth.

Initial tables:

- problems
- runs
- generations
- agents
- submissions
- evaluations
- jobs
- model_profiles
- model_calls
- run_events

The first worker queue should be PostgreSQL-backed, using a safe claim pattern such as `FOR UPDATE SKIP LOCKED`.

## Events

Use an append-only `run_events` table for auditability and live UI updates. This is not full event sourcing; relational tables remain canonical state.

Initial event names:

- RUN_CREATED
- RUN_STARTED
- GENERATION_CREATED
- AGENT_SPAWNED
- AGENT_STARTED
- AGENT_COMPLETED
- AGENT_FAILED
- JUDGING_STARTED
- EVALUATION_COMPLETED
- RUN_COMPLETED
- RUN_FAILED

## API and realtime

Use REST for commands and queries.

Examples:

```text
POST /problems
POST /runs
GET  /runs/{id}
POST /runs/{id}/pause
```

Use Server-Sent Events for server-to-browser live updates:

```text
GET /runs/{id}/events
```

SSE is preferred over WebSockets until bidirectional realtime interaction is actually needed.

## Configuration

Use environment variables through Pydantic settings for secrets and deployment-specific values.

Use YAML or equivalent declarative files for model profiles and routing defaults.

Model-quality estimates must eventually come from the project's own eval suite rather than intuition.

## Testing

The first provider implemented should be a deterministic FakeProvider.

The first integration test must be able to execute the complete baseline with no external API calls:

```text
problem
 -> 4 fake researchers
 -> 4 submissions
 -> 2 fake judges
 -> evaluations
 -> completed run
```

Only then should real providers be connected.
