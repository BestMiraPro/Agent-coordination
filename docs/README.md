# Documentation

The [top-level README](../README.md) is the current description of the system.
This directory holds decisions, setup notes and the design history.

## Decisions and setup

- [ADR-0001: Start as a modular monolith](adr/0001-modular-monolith.md): why
  the API, worker and orchestration share one Python codebase, with PostgreSQL
  as both canonical state and the job queue.
- [W&B Inference setup](wandb-inference.md): OpenAI-compatible inference,
  catalog discovery and credential handling.

## Design history

[`history/`](history/) holds the documents the system was built from:

- [`architecture-brief.md`](history/architecture-brief.md): the original
  Phase-0 architecture brief. It lists some modules and constraints that the
  implementation later changed or dropped.
- [`master-plan.md`](history/master-plan.md): the phased roadmap and the
  reasoning behind selection, judging, mutation and stopping rules.
- `phase-01.md` to `phase-10.md`: per-phase implementation contracts and
  acceptance criteria. The Phase 1 file has a separate implementation
  contract.

These files record what was planned at each step. They are kept for
traceability, but they are not a description of the current code.
