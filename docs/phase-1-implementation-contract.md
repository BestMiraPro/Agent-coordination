# Phase 1 Implementation Contract

This document turns the Phase 1 architecture into concrete work packages for coding agents.

## Status

- [x] Work package A — persistence foundation
- [x] Work package B — repository interfaces + SQLAlchemy implementations
- [x] Work package C — PostgreSQL durable job queue
- [ ] Work package D — baseline orchestrator
- [ ] Work package E — structured parsing
- [ ] Work package F — API
- [ ] Work package G — minimal web control room
- [ ] Work package H — baseline end-to-end integration test

## Work package A — Persistence foundation

Implement SQLAlchemy models and migrations for:

- problems
- runs
- generations
- agents
- submissions
- evaluations
- model_profiles
- model_calls
- jobs
- run_events

Requirements:

- PostgreSQL is canonical state.
- All IDs are UUIDs.
- Important timestamps use timezone-aware UTC.
- Jobs include idempotency keys, attempts, claim/lease metadata, and terminal status.
- Run events are append-only.
- Raw provider payload metadata is JSON-capable but must not become the primary domain representation.

Acceptance:

- schema can be created from scratch
- migrations upgrade cleanly
- repository integration tests use a real PostgreSQL instance

## Work package B — Repository interfaces

Create persistence interfaces and SQLAlchemy-backed implementations for:

- ProblemRepository
- RunRepository
- GenerationRepository
- AgentRepository
- SubmissionRepository
- EvaluationRepository
- ModelCallRepository
- JobRepository
- RunEventRepository

Core orchestration must depend on interfaces, not SQLAlchemy sessions.

## Work package C — Durable job queue

Implement PostgreSQL job claiming with concurrency-safe semantics.

Required job types:

- create_generation
- run_research_agent
- start_judging
- run_judge
- finalize_run

Requirements:

- atomic claim
- retry counter
- retry-after/backoff support
- terminal failure state
- idempotency
- duplicate execution must not duplicate durable state

## Work package D — Baseline orchestrator

Implement deterministic orchestration for exactly one generation.

Flow:

1. CREATED -> RESEARCHING
2. create Generation 0
3. create four researcher agents
4. enqueue four research jobs
5. when all researchers reach terminal state, enqueue judging
6. anonymize and shuffle submissions for judge context
7. run two judges independently
8. aggregate evaluations
9. JUDGING -> COMPLETED

The LLM never selects state transitions.

## Work package E — Structured parsing

Define strict schemas for researcher and judge outputs.

Requirements:

- preserve raw text
- validate parsed structure
- record parse failures explicitly
- permit bounded repair/retry policy
- never silently coerce malformed output into valid-looking research

## Work package F — API

Implement:

- POST /problems
- POST /runs
- GET /runs/{run_id}
- GET /runs/{run_id}/events

The run endpoint should expose enough nested state for a minimal inspection UI without requiring dozens of tiny requests.

SSE event streaming may initially poll the append-only event table if necessary.

## Work package G — Minimal web control room

Implement only:

- create-problem/run form
- run status
- researcher status
- submissions
- judge evaluations
- event timeline

No tournament graph yet.

## Work package H — Baseline integration test

A deterministic end-to-end test using FakeProvider must prove:

- problem created
- run created
- generation created
- four researchers execute
- four submissions persist
- two judges execute
- evaluations persist
- run completes
- expected events exist

Also test:

- researcher retry
- malformed output handling
- judge retry
- duplicate job execution

## Implementation order

1. persistence schema
2. repository interfaces
3. durable jobs
4. orchestrator
5. structured parsing
6. API
7. FakeProvider end-to-end integration test
8. minimal UI
9. one real provider

Do not connect multiple real providers until the fake baseline is green.
