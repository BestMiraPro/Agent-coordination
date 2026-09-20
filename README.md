# Agent Coordination

A research-oriented multi-agent coordination system designed to maximize verified research progress per unit of time and compute budget.

The current implementation includes the complete Phase 1 vertical slice and
Phase 2 autonomous tournament mechanics:

```text
problem
 -> Generation 0 independent researchers
 -> blind multidimensional judging
 -> vector-aware selection
 -> elimination
 -> clone surviving ideas
 -> mutate children
 -> persist lineage
 -> next generation
 -> ... until configured generation limit
```

The orchestration state machine, durable PostgreSQL queue, API, worker,
provider boundary, evolutionary policy, lineage persistence, and web control
room are implemented.

## Run the complete local stack

```bash
docker compose up --build
```

Then open the research tournament control room at `http://localhost:3000`.
The API is exposed at `http://localhost:8000`.

The default worker uses a deterministic fake provider, so a complete
multi-generation tournament can run without credentials.

## Tournament defaults

Runs created from the API/control room default to:

```text
generations: 3
population:  4
survivors:   2
judges:      2 per generation
```

Selection is based on the full evaluation vector rather than a single scalar.
Survivors are cloned with `STRENGTHEN`, `FALSIFY`, `REDERIVE`, and
`GENERALIZE` mutation objectives. Selection decisions and parent-child
lineage are durable and inspectable.

## Use W&B Inference

Create a local `.env` from `.env.example`, then set:

```bash
INFERENCE_PROVIDER=wandb
INFERENCE_API_KEY=<your W&B API key>
INFERENCE_MODEL=openai/gpt-oss-20b
INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
INFERENCE_PROJECT=<optional team/project>
```

The model can be replaced with another model available to your W&B account
without changing tournament code. No API key is persisted in the database or
repository.

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

CI runs PostgreSQL migrations, backend/unit/integration tests, provider
contracts, Docker Compose validation, and a production Next.js build.

## Architectural principles

- LLMs do research; code owns orchestration state.
- Agents are disposable; useful research artifacts are durable.
- Provider-specific logic never leaks into the core domain.
- Every model call is attributable, measurable, and retry-safe.
- Judges do not see model identity or lineage.
- Selection does not rely on one scalar fitness score.
- Convergence is not correctness; verification matters more than consensus.
- Infrastructure is added only when measurements justify it.

See `docs/architecture.md`, `docs/master-plan.md`,
`docs/phase-1-implementation-contract.md`, and `docs/phase-2.md`.
