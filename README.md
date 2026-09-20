# Agent Coordination

A durable AI research laboratory and software-engineering factory designed to
maximize verified progress per unit of wall-clock time and constrained compute
budget.

The repository implements the full Phase 0–10 master-plan path at its current
MVP/architecture boundary.

## Research workflow

```text
problem
 -> explicit research niches
 -> independent population
 -> structured submissions
 -> blind multidimensional judges
 -> novelty + redundancy analysis
 -> elite / novelty / wildcard survival
 -> persistent research memory
 -> selective cross-pollination
 -> cloned mutations + fresh blind explorers
 -> dedicated adversarial critics
 -> deterministic verification
 -> verified/refuted candidate lifecycle
 -> adaptive model routing
 -> control-room inspection and intervention
```

Research agents are disposable. Typed knowledge, lineage, selection decisions,
critic findings, verification results, model-call accounting, and events are
durable PostgreSQL state.

## Engineering workflow

```text
objective
 -> planner
 -> primary implementer + test specialist
 -> deterministic artifact checks
 -> system reviewer
 -> bounded repair loop
 -> re-test + re-review
 -> completed / failed
```

The engineering factory reuses the same provider abstraction, adaptive router,
durable PostgreSQL queue, retries, model-call accounting, and control room while
remaining separate from research-tournament selection policy.

## Implemented phases

| Phase | Capability | Status |
| --- | --- | --- |
| 0 | Stable provider/domain/repository/orchestration boundaries | Implemented |
| 1 | Baseline vertical research slice | Implemented |
| 2 | Multi-generation evolution, cloning, mutation, lineage | Implemented |
| 3 | Niches, novelty, redundancy, wildcards, fresh explorers | Implemented |
| 4 | Persistent typed research memory | Implemented |
| 5 | Selective targeted cross-pollination | Implemented |
| 6 | Dedicated critics and candidate lifecycle | Implemented |
| 7 | Deterministic verification framework and durable results | Implemented |
| 8 | Adaptive quality/cost/latency/scarcity routing | Implemented |
| 9 | Production-style research control room | Implemented |
| 10 | Separate durable engineering factory | Implemented |

Detailed contracts live in `docs/phase-1-implementation-contract.md` through
`docs/phase-10.md`.

## Run locally

```bash
docker compose up --build
```

Then open:

- control room: `http://localhost:3000`
- API: `http://localhost:8000`

The default worker uses a deterministic fake provider, so both research and
engineering workflows can be exercised without credentials.

## Real inference

The first production provider boundary is OpenAI-compatible inference, with W&B
Inference as the configured example.

Create `.env` from `.env.example` and set:

```bash
INFERENCE_PROVIDER=wandb
WANDB_API_KEY=<your W&B API key>
INFERENCE_MODEL=openai/gpt-oss-20b
INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
INFERENCE_PROJECT=<optional team/project>
INFERENCE_DISCOVER_MODELS=true
```

No API key is persisted in model profiles, model calls, or run state. With
W&B catalog discovery enabled, worker startup authenticates against the
documented `GET /models` endpoint and registers the currently available model
IDs with neutral routing priors. `INFERENCE_API_KEY` remains supported as the
vendor-neutral override.

The adaptive router has durable model-state support for task quality, marginal
cash cost, credit consumption, latency, scarcity, failures, rate-limit pressure,
and concurrency. A single-provider deployment is valid; adding more provider
routes does not require changing tournament or engineering orchestration.

## Research defaults

The control room currently defaults to:

```text
generations:          3
population:           6
survivors:            3
fresh explorers:      1 per later generation
critics:              1
redundancy threshold: 0.78
final verification:   enabled
judges:               2 per generation
```

With three survivor slots, policy reserves an elite, a novelty survivor, and a
deterministic wildcard where possible. Fatal or critic-refuted branches are
excluded while non-fatal alternatives exist.

Fresh explorers do not receive parent candidates, historical research memory,
or cross-pollination packets.

## Verification boundary

Verification is deliberately stronger than model consensus. The current
deterministic engine checks:

- survival of configured adversarial critics,
- explicit support for structured claims,
- Python syntax when Python code blocks are supplied.

The durable verifier interface is designed for additional sandbox, solver,
proof-assistant, and source/citation adapters. Those external systems are not
silently emulated: a candidate is only marked `VERIFIED` when the configured
deterministic checks actually pass.

## Engineering safety boundary

Generated engineering code is stored as structured artifacts. The current local
test runner performs deterministic non-executing checks for:

- artifact presence,
- safe relative paths,
- duplicate paths,
- Python compilation,
- JSON parsing,
- presence of test artifacts.

It intentionally does **not** execute arbitrary model-generated code on the
worker host. Real unit/integration/property/fuzz execution should be connected
through an isolated disposable sandbox rather than weakening this boundary.

## Development

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
make api
```

In separate terminals:

```bash
make worker
```

and:

```bash
cd apps/web
npm install
npm run dev
```

## Quality gates

```bash
pytest -q
ruff check .
cd apps/web && npm run build
```

CI validates Docker Compose, migrates PostgreSQL through all schema revisions,
runs unit/integration/provider/eval tests, and builds the production Next.js
control room.

## Core invariants

- deterministic code owns orchestration state;
- model identity stays hidden from blind research judges;
- selection never collapses to one scalar fitness score;
- diversity is protected without treating novelty as correctness;
- agents die, knowledge survives;
- cross-pollination is targeted rather than all-to-all;
- critic/refutation state affects later selection;
- verification outranks consensus;
- model routing accounts for quality, cost, latency, scarcity, and reliability;
- research and engineering share infrastructure but use different policies;
- untrusted generated code is not executed on the worker host.
