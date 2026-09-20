from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean
from uuid import UUID

from packages.core.domain.models import Evaluation, SelectionDecision, Submission


@dataclass(frozen=True, slots=True)
class AggregateEvaluation:
    submission_id: UUID
    fatal_error: bool
    correctness: float
    rigor: float
    novelty: float
    research_progress: float
    verifiability: float
    judge_confidence: float

    def as_vector(self) -> dict[str, float | bool]:
        return {
            "fatal_error": self.fatal_error,
            "correctness": self.correctness,
            "rigor": self.rigor,
            "novelty": self.novelty,
            "research_progress": self.research_progress,
            "verifiability": self.verifiability,
            "judge_confidence": self.judge_confidence,
        }


class TournamentPolicy:
    """Deterministic vector-aware Phase 2 selection policy.

    Selection is lexicographic rather than a single weighted scalar:
    fatal-error status first, then correctness, rigor, research progress,
    verifiability, novelty, and judge confidence.
    """

    def select(
        self,
        generation_id: UUID,
        submissions: list[Submission],
        evaluations: list[Evaluation],
        survivor_count: int,
    ) -> list[SelectionDecision]:
        if not submissions:
            raise ValueError("Cannot select from an empty generation")
        if survivor_count <= 0 or survivor_count > len(submissions):
            raise ValueError("survivor_count must be within the population")

        by_submission: dict[UUID, list[Evaluation]] = defaultdict(list)
        for evaluation in evaluations:
            by_submission[evaluation.submission_id].append(evaluation)

        aggregates: list[AggregateEvaluation] = []
        for submission in submissions:
            judged = by_submission.get(submission.id, [])
            if not judged:
                raise ValueError(f"Submission {submission.id} has no evaluations")
            aggregates.append(
                AggregateEvaluation(
                    submission_id=submission.id,
                    fatal_error=any(item.fatal_error for item in judged),
                    correctness=fmean(item.correctness for item in judged),
                    rigor=fmean(item.rigor for item in judged),
                    novelty=fmean(item.novelty for item in judged),
                    research_progress=fmean(item.research_progress for item in judged),
                    verifiability=fmean(item.verifiability for item in judged),
                    judge_confidence=fmean(item.judge_confidence for item in judged),
                )
            )

        ranked = sorted(
            aggregates,
            key=lambda item: (
                item.fatal_error,
                -item.correctness,
                -item.rigor,
                -item.research_progress,
                -item.verifiability,
                -item.novelty,
                -item.judge_confidence,
                str(item.submission_id),
            ),
        )

        decisions: list[SelectionDecision] = []
        for index, aggregate in enumerate(ranked, start=1):
            selected = index <= survivor_count
            decisions.append(
                SelectionDecision(
                    generation_id=generation_id,
                    submission_id=aggregate.submission_id,
                    selected=selected,
                    rank=index,
                    score_vector=aggregate.as_vector(),
                    reason=(
                        "selected for cloning by vector ranking"
                        if selected
                        else "eliminated after vector ranking"
                    ),
                )
            )
        return decisions
