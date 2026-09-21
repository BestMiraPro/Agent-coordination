# Phase 5 — Selective Cross-Pollination

Cross-pollination is staged and targeted rather than all-to-all.

After selection, each cloned child keeps its own selected parent and may receive
one compact packet from a different selected branch. Fresh explorers receive no
packet and remain blind.

Packets are durable and typed:

- `VERIFIED`
- `PROMISING`
- `REFUTED`
- `OPEN`
- `TRY`

The current tournament emits `PROMISING` or `TRY` packets from another
survivor, carrying only compact structured fields: summary, approach,
discoveries, and open questions. Raw transcripts are never transferred.

This keeps cross-pollination bounded to O(population) packets per generation
instead of an all-to-all context explosion.

Each packet records its source submission and exact target agent, so later
experiments can measure whether transferred ideas helped or caused correlated
failure.
