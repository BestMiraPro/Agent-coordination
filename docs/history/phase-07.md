# Phase 7 — External / Deterministic Verification

Phase 7 introduces a verifier boundary that is stronger than model consensus.

The initial verification engine is intentionally deterministic and local. It
implements three checks:

- adversarial survival: fatal critic findings fail verification,
- structured evidence: the candidate must have an explicit final answer and
  explicit support for each structured claim,
- Python compilation: when Python code blocks are present, every block must
  compile.

The engine returns typed, durable verification results with `PASSED`,
`FAILED`, or `INCONCLUSIVE` status.

On the final generation the tournament identifies the best non-refuted
candidate and, when verification is enabled, runs the verification engine before
completion. A fully passing candidate moves to `VERIFIED`; a failing candidate
moves to `REFUTED`; incomplete evidence remains in `VERIFICATION`.

This is the framework boundary for stronger task-specific adapters. Future
verifiers can add sandboxed test execution, SMT/SAT or symbolic solvers, proof
assistants, primary-source retrieval, citation checks, and reproducible
experiments without changing tournament selection or persistence.

Model agreement alone can never produce a `VERIFIED` lifecycle state.
