# Phase 6 — Adversarial Mode

Phase 6 adds a dedicated critic population and explicit candidate lifecycle.

Candidate states are durable:

- `PROPOSED`
- `PROMISING`
- `LEADING`
- `UNDER_ATTACK`
- `VERIFICATION`
- `VERIFIED`
- `REFUTED`

After blind judging, a deterministic preview identifies the leading viable
candidate. Dedicated critic agents receive the original problem and that
candidate only. Their prompt rewards finding genuine fatal flaws,
counterexamples, hidden assumptions, or unsupported steps rather than agreement.

Critic output is separately structured as fatal-error status, confidence,
critique, and optional counterexample.

A candidate moves to `REFUTED` when any configured critic finds a fatal flaw;
otherwise it moves to `VERIFICATION`. Refuted submissions are treated as fatal
by later tournament selection even if ordinary judges scored them highly.

Critic agents are durable agents with retry/idempotency behavior identical to
researchers and judges. Their findings and lifecycle transitions are persisted
and exposed through the API.
