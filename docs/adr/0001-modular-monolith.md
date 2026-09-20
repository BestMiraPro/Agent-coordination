# ADR-0001: Start as a Modular Monolith

## Status

Accepted.

## Decision

Use a Python modular monolith for the API, worker, orchestration core, providers, and persistence boundaries, with a separate Next.js frontend.

Use PostgreSQL as both canonical application storage and the initial durable job queue.

## Rationale

The project is still validating its orchestration algorithms. Microservices, dedicated workflow engines, distributed queues, and extra data stores would create operational and conceptual overhead before the workload is known.

Strict internal package boundaries preserve the option to split services later without paying that cost now.

## Consequences

Positive:

- faster iteration
- simpler local development
- simpler testing
- easier transactional correctness
- less infrastructure cost

Tradeoff:

- scaling boundaries are logical rather than physical at first

This is intentional and should be revisited only after measurements show a bottleneck.
