# Phase 1 Implementation Contract

This document turns the Phase 1 architecture into concrete work packages for coding agents.

## Status

- [x] Work package A — persistence foundation
- [x] Work package B — repository interfaces + SQLAlchemy implementations
- [x] Work package C — PostgreSQL durable job queue
- [x] Work package D — baseline orchestrator
- [x] Work package E — structured parsing
- [x] Work package F — API
- [x] Work package G — minimal web control room
- [ ] Work package H — baseline end-to-end integration test

## Work package G — Minimal web control room

Implemented a Next.js control room with:

- problem/run creation,
- live run state and counts,
- researcher and judge status,
- structured submissions,
- evaluation scores and critiques,
- live Server-Sent Events timeline,
- polling fallback if SSE is temporarily unavailable,
- responsive layout for desktop and mobile.

The web application talks to the FastAPI service through
`NEXT_PUBLIC_API_BASE_URL`. The API accepts configured browser origins through
`WEB_ORIGIN`.

## Work package H — Baseline integration hardening

The existing deterministic baseline integration test proves the happy-path run.
Before Phase 1 is declared complete, add explicit integration coverage for:

- researcher retry after provider failure,
- malformed researcher output retry/failure,
- judge retry after provider failure,
- duplicate job execution without duplicate durable state.

After these paths are green, connect the first real provider.
