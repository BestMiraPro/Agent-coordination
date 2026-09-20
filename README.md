# Agent Coordination

A research-oriented multi-agent coordination system designed to maximize verified research progress per unit of time and compute budget.

The project begins deliberately small: deterministic orchestration, heterogeneous model providers, persistent run state, structured submissions, independent judging, and a minimal control room. Evolutionary search, research memory, cross-pollination, adversarial critics, and adaptive scheduling are added only after the baseline vertical slice is measured.

## Principles

- LLMs do research; code owns orchestration state.
- Agents are disposable; useful research artifacts are durable.
- Provider-specific logic never leaks into the core domain.
- Every model call is attributable, measurable, and retry-safe.
- Judges do not see model identity.
- Convergence is not correctness; verification matters more than consensus.
- Infrastructure is added when measurements justify it.

See `docs/architecture.md`, `docs/master-plan.md`, and `docs/phase-1.md` for the frozen architecture and implementation plan.
