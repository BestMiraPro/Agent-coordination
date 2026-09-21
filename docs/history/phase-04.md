# Phase 4 — Persistent Research Memory

Phase 4 separates agent lifetime from knowledge lifetime.

Every structured researcher submission is compacted into durable knowledge
objects. Claims, approaches, discoveries, failed attempts, open questions, and
candidate answers are persisted independently of the agent that produced them.

Knowledge kinds include verified/likely facts, hypotheses, candidate lemmas,
counterexamples, contradictions, failed and promising approaches, observations,
unresolved questions, and candidate solutions.

The initial extractor is deterministic. It does not pretend to verify claims:
high-confidence supported claims become `LIKELY_FACT`, not `VERIFIED_FACT`.
Verification in Phase 7 is the only component allowed to promote items to a
verified state.

Before a cloned researcher runs in a later generation, the worker constructs a
bounded research-memory packet from prior generations. It is sorted by status,
knowledge value, and confidence and deduplicated by normalized content.

Fresh Phase 3 explorers remain blind: they receive no parent candidate and no
historical research memory. That preserves an independent exploration channel.

The system never passes full historical transcripts. It passes only compact,
typed research state with provenance.

Acceptance is covered by unit extraction/compaction tests and a PostgreSQL
integration test proving that later cloned agents can access prior durable
memory while fresh agents remain isolated.
