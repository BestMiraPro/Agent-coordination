# Phase 8 — Adaptive Resource Allocation

Phase 8 introduces a provider-neutral routing layer.

Every model profile can have a durable operational state containing:

- task-specific quality estimates,
- marginal cash cost,
- credit cost,
- observed latency,
- scarcity,
- recent failure rate,
- rate-limit pressure,
- available concurrency,
- enabled/disabled state.

The `AdaptiveRouter` estimates task utility from expected quality and
reliability divided by weighted cost, latency, scarcity, and rate-limit
pressure. Concurrency provides a small positive capacity bonus.

The worker now goes through `AdaptiveProvider`, even when only one provider is
configured. This means adding a second provider does not require changes to
research orchestration, prompts, judges, or persistence.

Each routed response records the selected model-profile ID and routing utility.
Successful and failed calls feed observations back into durable model state,
updating latency and failure-rate estimates.

The API exposes `GET /model-states` for the control room.

The default single-provider deployment is intentionally conservative: routing
is live but trivial until multiple model routes are configured. This keeps
Phase 8 testable without requiring paid credentials while preserving the
architecture needed for Muse/W&B/other-model fallback pools.
