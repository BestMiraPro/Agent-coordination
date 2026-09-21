# Phase 1 Implementation Contract

## Status

- [x] Work package A — persistence foundation
- [x] Work package B — repository interfaces + SQLAlchemy implementations
- [x] Work package C — PostgreSQL durable job queue
- [x] Work package D — baseline orchestrator
- [x] Work package E — structured parsing
- [x] Work package F — API
- [x] Work package G — minimal web control room
- [x] Work package H — failure-path integration hardening
- [x] First real provider adapter — W&B/OpenAI-compatible inference
- [x] Runnable local stack — PostgreSQL + API + worker + web

## Phase 1 acceptance

The baseline now proves:

- problem and run creation,
- exactly one Generation 0,
- four independent research agents,
- strict structured researcher outputs,
- two model-blind judges,
- eight multidimensional evaluations,
- deterministic run-state transitions,
- durable PostgreSQL jobs,
- retries with exponential production backoff,
- terminal failure after retry exhaustion,
- malformed-output retry and terminal failure behavior,
- duplicate execution without duplicate research artifacts,
- raw model output retention,
- model-call accounting,
- Server-Sent Events,
- a minimal live web control room,
- a deterministic credential-free local provider,
- a real OpenAI-compatible provider boundary configured for W&B Inference.

Phase 1 is complete when CI is green.

## Real-provider configuration

The worker defaults to `INFERENCE_PROVIDER=fake`.

For W&B Inference:

```text
INFERENCE_PROVIDER=wandb
INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
INFERENCE_API_KEY=<secret>
INFERENCE_MODEL=openai/gpt-oss-20b
INFERENCE_PROJECT=<optional team/project>
INFERENCE_STRUCTURED_OUTPUTS=true
```

The API key is read only by the worker process and is never stored in model profile metadata or model-call records.

The provider supports strict JSON-schema response formatting when the selected endpoint/model supports it. It can be disabled with `INFERENCE_STRUCTURED_OUTPUTS=false`; prompts still demand JSON, and local validation remains strict.

## Next phase

Phase 2 introduces evolutionary mechanics only after this baseline is benchmarked:

- generation transitions,
- selection,
- elimination,
- cloning,
- mutation,
- lineage tracking.

Before optimizing tournament mechanics, compare this baseline against single-model and best-of-N baselines on an objective evaluation suite.
