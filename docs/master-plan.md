# Master Plan

## Product objective

Build a general-purpose AI research laboratory that can discover, preserve, challenge, verify, and synthesize candidate solutions under heterogeneous model budgets and rate limits.

The system evolves from a simple baseline into an adaptive research tournament only after each mechanism proves value in benchmark experiments.

## Product loop

Long-term target:

```text
problem
 -> diverse research niches
 -> independent population
 -> submissions
 -> multidimensional evaluation
 -> preserve best + novel + dissenting branches
 -> eliminate low-value/redundant branches
 -> clone ideas with mutation
 -> selective cross-pollination
 -> adversarial critics
 -> external verification
 -> final synthesis
```

The guiding rule is: agents die, knowledge survives.

## Development phases

### Phase 0 — Freeze abstractions

Define and stabilize:

- ModelProvider
- Problem
- Run
- Generation
- Agent
- Submission
- Evaluation
- Job
- RunEvent
- TournamentPolicy boundary
- persistence interfaces

Acceptance condition: core abstractions can be tested without network calls or framework dependencies.

### Phase 1 — Baseline vertical slice

Build:

- problem creation
- run creation
- one generation
- 4 independent researchers
- 2 independent judges
- structured submissions
- multidimensional evaluations
- persistence
- durable jobs
- model-call accounting
- event log
- minimal run inspection UI
- FakeProvider

Acceptance condition: the full run completes deterministically in integration tests.

### Phase 2 — Tournament mechanics

Add:

- generation transitions
- selection
- elimination
- cloning
- mutation
- lineage tracking

Acceptance condition: an autonomous multi-generation tournament can run end-to-end.

### Phase 3 — Diversity preservation

Add:

- explicit research niches
- novelty scoring
- wildcard survivors
- redundancy detection
- fresh blind-agent injection

Acceptance condition: the system resists premature convergence on benchmark tasks.

### Phase 4 — Persistent research memory

Add durable knowledge objects for:

- verified facts
- likely facts
- hypotheses
- candidate lemmas
- counterexamples
- contradictions
- failed approaches
- promising approaches
- unresolved questions

Acceptance condition: agents inherit compact research state instead of full transcripts.

### Phase 5 — Cross-pollination

Add compact transfer packets such as:

- VERIFIED
- PROMISING
- REFUTED
- OPEN
- TRY

Cross-pollination is selective and staged, never all-to-all by default.

### Phase 6 — Adversarial mode

Add dedicated critics and candidate lifecycle states:

- PROPOSED
- PROMISING
- LEADING
- UNDER_ATTACK
- VERIFICATION
- VERIFIED
- REFUTED

Critics are rewarded for finding fatal flaws, not for consensus.

### Phase 7 — External verification

Add deterministic or formal verification depending on task type.

For code:
- compiler/type checker
- unit tests
- integration tests
- property/fuzz tests
- benchmarks

For math:
- numerical checks
- symbolic checks
- solver-assisted checks
- proof assistants where appropriate

For factual research:
- primary-source retrieval
- independent source agreement
- citation/claim correspondence
- freshness checks

### Phase 8 — Adaptive resource allocation

Route compute according to estimated information value.

Track per-model:

- quality by task type
- latency
- cost/credit usage
- rate-limit pressure
- concurrency
- failures
- context/tool capabilities

Use Muse opportunistically and W&B-backed models as dependable automated capacity.

### Phase 9 — Production control room

Build views for:

- projects
- runs
- populations
- lineages
- submissions
- evaluations
- knowledge
- contradictions
- candidates
- verification
- models
- budgets
- metrics
- events

Manual intervention remains possible at all times.

### Phase 10 — Engineering workflow

Reuse common infrastructure for a separate software-engineering mode:

```text
planner
 -> specialized implementers
 -> deterministic tests
 -> reviewers
 -> repair
 -> final system review
```

Research and engineering workflows share providers, scheduling, persistence, metrics, and verification infrastructure, but use different orchestration policies.

## Selection philosophy

Never select only the top scalar score.

Survival should eventually preserve a mixture of:

- elites
- novel approaches
- counterexample finders
- useful dissent
- promising incomplete branches
- occasional wildcards

Diversity is a resource, not noise.

## Judge architecture

Long-term judging should separate responsibilities:

- correctness
- adversarial error finding
- research usefulness/novelty
- evidence/verification quality

Judges should be blind to author/model identity and prior scores where possible.

High judge disagreement is treated as uncertainty and should trigger more investigation.

## Mutation strategy

Clone ideas, not personas.

Useful child objectives include:

- strengthen the parent
- falsify the parent
- rederive independently
- combine with another branch
- prove a missing lemma
- search special cases
- generalize
- search computational counterexamples

## Stopping rules

A run may stop when:

- a candidate passes strong verification
- fresh critics repeatedly fail to break it
- no meaningful progress occurs for several generations
- all branches are refuted and a restart is needed
- the configured budget is exhausted
- judge disagreement remains high and policy escalates

Convergence alone is never a stopping proof.

## Metrics

Track at least:

- TimeToVerifiedSolution
- VerifiedInsightsPerGeneration
- VerifiedInsightsPerMillionTokens
- BranchDiversity
- JudgeDisagreement
- FalseConsensusRate
- ExternalVerificationPassRate
- cost/credit per verified insight
- wall-clock research progress

The principal optimization target is verified research progress per wall-clock time and constrained budget.

## Eval-driven development

Before adding expensive orchestration mechanisms, maintain a benchmark suite of known problems with objective checks.

Ablation order:

1. one strong model
2. best-of-N
3. tournament
4. tournament + memory
5. + cross-pollination
6. + critics
7. + adaptive routing

Keep only mechanisms that measurably improve verified outcomes.
