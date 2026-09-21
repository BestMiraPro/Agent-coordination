# Phase 9 — Production Control Room

Phase 9 turns the earlier live-run page into an operational research control room.

The backend now has first-class projects and dashboard endpoints for run lists,
model routing state, aggregate run metrics, and manual durable-knowledge
injection.

The control room surfaces:

- projects and run configuration,
- populations, niches, origins, and agent status,
- lineages and mutation history,
- submissions and multidimensional evaluations,
- selection, novelty, and redundancy,
- persistent knowledge and contradiction watch,
- selective cross-pollination packets,
- candidate lifecycle and critic findings,
- deterministic verification results,
- model quality/cost/latency/scarcity/rate-limit state,
- token/cost/run metrics,
- the complete event stream.

Manual intervention is intentionally bounded: operators can inject typed,
durable research knowledge with provenance. That knowledge becomes part of
future compact research memory without altering already-running blind agents.

The UI remains a single responsive Next.js control room rather than splitting
into premature micro-frontends. All state comes from the same persisted
research model used by workers and tests.
