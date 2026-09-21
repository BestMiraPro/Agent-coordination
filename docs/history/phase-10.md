# Phase 10 — Engineering Workflow

Phase 10 adds a separate durable software-engineering factory while reusing the
same provider abstraction, adaptive router, PostgreSQL persistence, durable job
queue, retry semantics, and model-call accounting.

The workflow is:

```text
planner
 -> primary implementer + test specialist
 -> deterministic artifact checks
 -> final system reviewer
 -> repair engineer when needed
 -> deterministic re-test
 -> final review
 -> completed / failed
```

Engineering runs are separate from research tournaments so research selection
mechanics do not leak into code production.

Generated implementations are structured file artifacts. The deterministic test
runner currently enforces:

- at least one generated file,
- sandbox-safe relative paths,
- unique file paths,
- Python compilation,
- JSON parsing,
- presence of a test artifact.

These are static checks, not a substitute for a real repository sandbox. The
boundary is intentionally designed so Phase 7-style sandboxed unit,
integration, property, fuzz, and benchmark execution can replace or augment
these checks without changing the orchestration state machine.

The reviewer is not allowed to approve while deterministic checks fail. Failed
reviews enter a bounded repair loop controlled by `max_repairs`.

Engineering model calls use the same adaptive provider and are attributed to a
durable engineering-run ID, preserving cost and latency accounting.

API endpoints expose creation, listing, and full inspection of engineering
runs, artifacts, checks, repair cycles, and status.
