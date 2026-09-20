# Agent Coordination

A research-oriented multi-agent coordination system designed to maximize
verified research progress per unit of time and constrained compute budget.

The repository now implements Phases 1–3:

```text
problem
 -> explicit research niches
 -> independent research population
 -> blind multidimensional judging
 -> quality + novelty + redundancy analysis
 -> elite / novelty / wildcard survival
 -> eliminate low-value or redundant branches
 -> clone surviving ideas with mutation
 -> inject fresh blind explorers
 -> persist lineage and diversity decisions
 -> next generation
 -> ... until configured generation limit
```

The orchestration state machine, durable PostgreSQL queue, API, worker,
provider boundary, evolutionary policy, diversity policy, lineage persistence,
and live web control room are implemented.

## Run the complete local stack

```bash
docker compose up --build
```

Open the control room at `http://localhost:3000`.
The API is exposed at `http://localhost:8000`.

The default worker uses a deterministic fake provider, so a complete
multi-generation diversity-preserving tournament runs without credentials.

## Tournament defaults

Runs created through the API/control room default to:

```text
generations:          3
population:           4
survivors:            2
fresh explorers:      1 per later generation
redundancy threshold: 0.78
judges:               2 per generation
```

With three or more survivor slots the selection policy explicitly reserves
elite, novelty, and wildcard survival. With two slots it preserves an elite and
a novelty branch.

Research agents rotate through explicit constructive, skeptical,
counterexample, computational, special-case, generalization,
alternative-formulation, and lemma-decomposition niches.

Novelty and redundancy are currently measured with deterministic lexical
Jaccard similarity over structured submission content. This costs no additional
model calls and provides a benchmarkable baseline before considering embeddings.

## Use W&B Inference

Create a local `.env` from `.env.example`, then set:

```bash
INFERENCE_PROVIDER=wandb
INFERENCE_API_KEY=<your W&B API key>
INFERENCE_MODEL=openai/gpt-oss-20b
INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
INFERENCE_PROJECT=<optional team/project>
```

The model can be replaced with another model available to the configured
OpenAI-compatible endpoint without changing tournament orchestration. API keys
are not persisted in the database or repository.

## Development without Docker

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
make api
```

In another terminal:

```bash
make worker
```

And in another:

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

CI validates Docker Compose, applies all PostgreSQL migrations, runs backend
unit/integration/provider/eval tests, and builds the production Next.js app.

## Architectural principles

- LLMs do research; deterministic code owns orchestration state.
- Agents are disposable; useful research artifacts should become durable.
- Provider-specific logic never leaks into the core domain.
- Every model call is attributable, measurable, and retry-safe.
- Judges do not see model identity, niche, origin, or lineage metadata.
- Selection never relies on one scalar fitness score.
- Diversity is protected without treating novelty as correctness.
- Fresh blind exploration remains available after convergence pressure begins.
- Convergence is not correctness; verification outranks consensus.
- Infrastructure is added only when measurements justify it.

See `docs/architecture.md`, `docs/master-plan.md`,
`docs/phase-1-implementation-contract.md`, `docs/phase-2.md`, and
`docs/phase-3.md`.
