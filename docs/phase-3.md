# Phase 3 — Diversity Preservation

## Purpose

Prevent a strong early lineage from collapsing the tournament into one family of
near-duplicate answers before alternative solution paths have been tested.

Phase 3 keeps correctness primary while treating diversity as a resource that is
explicitly measured, persisted, and budgeted.

## Research niches

Every researcher has one durable niche:

- `CONSTRUCTIVE`
- `SKEPTICAL`
- `COUNTEREXAMPLE`
- `COMPUTATIONAL`
- `SPECIAL_CASES`
- `GENERALIZATION`
- `ALTERNATIVE_FORMULATION`
- `LEMMA_DECOMPOSITION`

Niches are assigned deterministically across the population and rotated between
generations. The niche objective is included in the researcher prompt but is
never revealed to blind judges.

The niche is not a claim that the model actually uses that methodology. It is a
controlled prompt-level intervention whose effect can be measured in evals.

## Novelty scoring

Phase 3 adds a deterministic, local novelty signal.

For each structured submission, the system tokenizes:

- summary,
- approach,
- claims and claim support,
- evidence,
- discoveries,
- failed attempts,
- open questions,
- final answer.

It computes pairwise Jaccard similarity over normalized token sets.

```text
text_novelty = 1 - maximum_similarity_to_any_other_submission
```

This deliberately requires no embedding model, vector database, or extra API
call. It is cheap, reproducible, and suitable as the first diversity heuristic.

It is not treated as semantic truth. Later evals may justify replacing or
augmenting it with learned embeddings or task-specific structural metrics.

## Redundancy detection

A submission is marked redundant when its similarity to a higher quality-ranked
submission is at or above the run's `redundancy_threshold`.

The default threshold is `0.78`.

Every selection decision persists:

- novelty score,
- maximum similarity in the score vector,
- redundant-with submission ID when applicable,
- selection kind,
- reason.

Redundancy is not an automatic correctness penalty. It primarily prevents all
survivor slots from being consumed by the same answer family.

## Survivor allocation

The policy remains vector-aware and never uses one scalar fitness score.

When the survivor budget permits, selection reserves:

1. one `ELITE` slot for the strongest viable branch,
2. one `NOVELTY` slot for the most textually novel viable branch,
3. one `WILDCARD` slot selected deterministically from the remaining viable
   non-redundant branches.

Any remaining survivor slots use `QUALITY` selection while preferring branches
that are not redundant with already-selected survivors.

If there are fewer than three survivor slots, the policy degrades gracefully:
elite first, then novelty, then quality.

Fatal-error branches remain excluded while any non-fatal alternative exists.

## Wildcards

The wildcard is deterministic for a given generation and candidate set. Its
choice is based on a hash of the generation ID and submission ID rather than
model preference or prior score.

This gives the tournament a small amount of controlled exploration without
making tests irreproducible.

## Fresh blind-agent injection

A run can reserve `fresh_agent_count` slots in every generation after the first.

Fresh agents:

- have `origin=FRESH`,
- have no parent lineage,
- receive no parent submission,
- receive no prior tournament candidate,
- still receive an explicit research niche.

The remaining slots are cloned descendants of selected survivors.

Domain-level defaults preserve Phase 2 behavior with zero fresh agents. The API
and control room default to one fresh explorer per generation.

## Agent origin

Researchers persist one of:

- `INITIAL` — Generation 0 independent researcher,
- `CLONED` — descendant of a selected parent,
- `FRESH` — blind exploration injection.

This lets later evals compare whether useful discoveries come from exploitation
or fresh exploration.

## Events

Phase 3 adds:

- `DIVERSITY_ANALYZED`
- `REDUNDANCY_DETECTED`
- `WILDCARD_SELECTED`
- `FRESH_AGENT_INJECTED`

Existing branch selection and lineage events now include diversity metadata.

## Control room

The web UI exposes:

- fresh-agent count,
- redundancy threshold,
- active research niches,
- agent origin,
- selection kind,
- text novelty score,
- redundancy links,
- diversity-related run events.

## Acceptance evidence

Phase 3 includes three layers of deterministic evidence.

Unit tests prove:

- redundancy links point to a higher-ranked duplicate,
- novel branches can survive over stronger duplicates,
- a three-survivor budget contains elite, novelty, and wildcard selections,
- selection remains deterministic.

An eval-style benchmark creates a synthetic premature-convergence scenario in
which naive top-k selection chooses three members of the same high-scoring
family. The Phase 3 policy must retain at least one independent alternative and
therefore preserve more approach families than top-k.

The end-to-end PostgreSQL integration test runs a three-generation tournament
with:

- population 6,
- 3 survivors,
- 1 fresh blind explorer per new generation,
- six distinct niches per generation,
- five cloned descendants plus one fresh explorer in each later generation,
- elite + novelty + wildcard survival,
- persistent lineage only for cloned agents,
- fresh model calls with no parent submission metadata,
- diversity events in the audit log.

## Definition of done

Phase 3 is complete when the diversity benchmark, full multi-generation
integration test, database migrations, API, control room, and production web
build all pass CI.

Phase 4 is persistent research memory. It should preserve durable discoveries
and failures independently of agent survival, rather than increasing population
size or prompt history.
