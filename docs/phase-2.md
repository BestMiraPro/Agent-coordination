# Phase 2 — Tournament Mechanics

## Purpose

Turn the Phase 1 single-generation baseline into an autonomous evolutionary
research tournament while preserving deterministic orchestration and durable
auditability.

## Implemented loop

```text
Generation N
  -> researchers
  -> structured submissions
  -> two blind judges
  -> multidimensional evaluations
  -> vector-aware selection
  -> survivors + eliminations recorded
  -> survivors cloned into a full next population
  -> deterministic mutation objectives
  -> lineage links persisted
  -> Generation N+1
```

The run completes after its configured `max_generations`.

## Run configuration

Every run stores:

- `max_generations`
- `population_size`
- `survivor_count`

The API defaults to 3 generations, 4 researchers per generation, and 2
survivors. The domain default remains one generation so existing baseline tests
remain explicit and backwards compatible.

## Selection policy

Phase 2 deliberately does **not** collapse judging into one scalar fitness score.

Each submission is aggregated across judges and ranked lexicographically by:

1. absence of a fatal error,
2. correctness,
3. rigor,
4. research progress,
5. verifiability,
6. novelty,
7. judge confidence.

Every candidate receives a durable `SelectionDecision` containing:

- rank,
- selected/eliminated status,
- the aggregated score vector,
- the decision reason.

This is still intentionally simple. Diversity quotas, wildcard survival, and
redundancy-aware selection belong to Phase 3.

## Mutation policy

Children inherit one selected parent submission and receive one deterministic
mutation objective:

- `STRENGTHEN`
- `FALSIFY`
- `REDERIVE`
- `GENERALIZE`

The four objectives cycle across the child population. For larger populations,
the cycle repeats and parents are assigned round-robin across survivors.

Mutation prompts include compact structured parent state, not the parent's raw
transcript. Children are instructed to produce a genuinely new candidate rather
than paraphrasing the parent.

## Lineage

Every cloned child has one durable `LineageLink`:

```text
child_agent_id
parent_submission_id
mutation_type
```

This is intentionally a single-parent lineage in Phase 2. Multi-parent
recombination belongs to later cross-pollination work.

## Idempotency and stale-job safety

Generation-scoped judge/finalize jobs carry the generation ID.

This prevents delayed jobs from accidentally judging or finalizing a newer
generation. Replaying an old finalizer does not create an extra generation.
Terminal runs ignore stale finalization work.

## Events

Phase 2 adds:

- `SELECTION_COMPLETED`
- `BRANCH_SELECTED`
- `BRANCH_ELIMINATED`
- `AGENT_CLONED`
- `GENERATION_ADVANCED`

The web control room renders the current generation plus selection and lineage
history.

## Acceptance tests

Phase 2 is accepted when CI proves an autonomous three-generation tournament:

- 3 generations,
- 4 researchers per generation,
- 2 judges per generation,
- 4 submissions and 8 evaluations per generation,
- 2 survivor decisions after each non-final generation,
- 4 lineage links in each cloned generation,
- all four mutation strategies represented,
- parent links point to the immediately preceding generation,
- replaying an old finalizer creates no duplicate generation,
- the run reaches `COMPLETED`.

## Definition of done

Phase 2 is complete when the deterministic tournament runs end-to-end with no
network calls, the full evolution history is persisted and exposed by the API,
the control room displays it, and backend + frontend CI are green.
