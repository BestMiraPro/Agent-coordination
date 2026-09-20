# Agent Coordination

A research-oriented multi-agent coordination system designed to maximize verified research progress per unit of time and compute budget.

Phase 1 is a working vertical slice:

```text
problem
 -> 4 independent researchers
 -> structured submissions
 -> 2 blind judges
 -> 8 multidimensional evaluations
 -> completed run
```

The orchestration state machine, durable PostgreSQL queue, API, worker, model-provider boundary, and web control room are implemented. The runtime defaults to a deterministic fake provider so the whole stack can run without credentials.

## Run the complete local stack

```bash
docker compose up --build
```

Then open the web control room at `http://localhost:3000`.

The API is exposed at `http://localhost:8000`. PostgreSQL is exposed at `localhost:5432`.

## Use W&B Inference

The first real provider is W&B Inference through its OpenAI-compatible chat-completions endpoint.

Create a local `.env` from `.env.example`, then set:

```bash
INFERENCE_PROVIDER=wandb
INFERENCE_API_KEY=<your W&B API key>
INFERENCE_MODEL=openai/gpt-oss-20b
INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
INFERENCE_PROJECT=<optional team/project>
```

You can replace `INFERENCE_MODEL` with another model available to your W&B account without changing orchestration code.

Then start the stack normally:

```bash
docker compose up --build
```

No API key is stored in the repository or model-call metadata.

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

CI runs PostgreSQL migrations, backend/integration tests, and a production Next.js build.

## Architectural principles

- LLMs do research; code owns orchestration state.
- Agents are disposable; useful research artifacts are durable.
- Provider-specific logic never leaks into the core domain.
- Every model call is attributable, measurable, and retry-safe.
- Judges do not see model identity.
- Convergence is not correctness; verification matters more than consensus.
- Infrastructure is added only when measurements justify it.

See `docs/architecture.md`, `docs/master-plan.md`, and
`docs/phase-1-implementation-contract.md`.
