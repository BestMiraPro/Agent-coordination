from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from statistics import fmean
from uuid import UUID

from packages.core.domain.models import (
    Evaluation,
    SelectionDecision,
    SelectionKind,
    Submission,
)


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "with",
}


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
            "judge_novelty": self.novelty,
            "research_progress": self.research_progress,
            "verifiability": self.verifiability,
            "judge_confidence": self.judge_confidence,
        }


@dataclass(frozen=True, slots=True)
class DiversitySignal:
    novelty_score: float
    max_similarity: float
    redundant_with_submission_id: UUID | None


class TournamentPolicy:
    """Deterministic Phase 3 selection policy.

    The policy keeps correctness primary while reserving diversity slots.
    It selects an elite, then a textually novel survivor, then a deterministic
    wildcard when enough survivor slots exist. Remaining slots are filled by
    quality while avoiding redundant branches whenever an alternative exists.
    """

    def select(
        self,
        generation_id: UUID,
        submissions: list[Submission],
        evaluations: list[Evaluation],
        survivor_count: int,
        redundancy_threshold: float = 0.78,
    ) -> list[SelectionDecision]:
        if not submissions:
            raise ValueError("Cannot select from an empty generation")
        if survivor_count <= 0 or survivor_count > len(submissions):
            raise ValueError("survivor_count must be within the population")
        if not 0.0 <= redundancy_threshold <= 1.0:
            raise ValueError("redundancy_threshold must be between 0 and 1")

        aggregates = self._aggregate(submissions, evaluations)
        ranked = sorted(aggregates, key=self._quality_key)
        rank_by_id = {
            aggregate.submission_id: index
            for index, aggregate in enumerate(ranked, start=1)
        }
        aggregate_by_id = {item.submission_id: item for item in aggregates}

        diversity = self._diversity_signals(
            submissions=submissions,
            quality_rank=rank_by_id,
            redundancy_threshold=redundancy_threshold,
        )

        nonfatal_ids = [
            item.submission_id for item in ranked if not item.fatal_error
        ]
        viable_ids = nonfatal_ids or [item.submission_id for item in ranked]

        selected_kind: dict[UUID, SelectionKind] = {}

        def add(submission_id: UUID | None, kind: SelectionKind) -> None:
            if submission_id is not None and len(selected_kind) < survivor_count:
                selected_kind.setdefault(submission_id, kind)

        # Always preserve the strongest viable branch.
        add(viable_ids[0] if viable_ids else None, SelectionKind.ELITE)

        # Reserve one novelty slot when possible.
        if survivor_count >= 2:
            novelty_candidates = [
                submission_id
                for submission_id in viable_ids
                if submission_id not in selected_kind
            ]
            novelty_candidates.sort(
                key=lambda submission_id: (
                    -diversity[submission_id].novelty_score,
                    rank_by_id[submission_id],
                    str(submission_id),
                )
            )
            add(novelty_candidates[0] if novelty_candidates else None, SelectionKind.NOVELTY)

        # Reserve one deterministic wildcard slot when the survivor budget permits.
        if survivor_count >= 3:
            wildcard_candidates = [
                submission_id
                for submission_id in viable_ids
                if submission_id not in selected_kind
                and not self._redundant_with_selected(
                    submission_id,
                    selected_kind,
                    submissions,
                    redundancy_threshold,
                )
            ]
            if not wildcard_candidates:
                wildcard_candidates = [
                    submission_id
                    for submission_id in viable_ids
                    if submission_id not in selected_kind
                ]
            wildcard_candidates.sort(
                key=lambda submission_id: sha256(
                    f"{generation_id}:{submission_id}:wildcard".encode()
                ).digest()
            )
            add(
                wildcard_candidates[0] if wildcard_candidates else None,
                SelectionKind.WILDCARD,
            )

        # Fill remaining survivor slots by quality, preferring non-redundant branches.
        for allow_redundant in (False, True):
            for aggregate in ranked:
                submission_id = aggregate.submission_id
                if len(selected_kind) >= survivor_count:
                    break
                if submission_id in selected_kind:
                    continue
                if nonfatal_ids and aggregate.fatal_error:
                    continue
                if (
                    not allow_redundant
                    and self._redundant_with_selected(
                        submission_id,
                        selected_kind,
                        submissions,
                        redundancy_threshold,
                    )
                ):
                    continue
                add(submission_id, SelectionKind.QUALITY)

        decisions: list[SelectionDecision] = []
        for aggregate in ranked:
            submission_id = aggregate.submission_id
            signal = diversity[submission_id]
            selected = submission_id in selected_kind
            if selected:
                kind = selected_kind[submission_id]
                reason = {
                    SelectionKind.ELITE: "selected as highest-quality viable elite",
                    SelectionKind.NOVELTY: "selected to preserve a textually novel branch",
                    SelectionKind.WILDCARD: "selected as deterministic wildcard survivor",
                    SelectionKind.QUALITY: "selected by quality after diversity quotas",
                }[kind]
            elif signal.redundant_with_submission_id is not None:
                kind = SelectionKind.REDUNDANT
                reason = "eliminated as redundant with a higher-ranked branch"
            else:
                kind = SelectionKind.ELIMINATED
                reason = "eliminated after quality and diversity selection"

            vector = aggregate.as_vector()
            vector.update(
                {
                    "text_novelty": signal.novelty_score,
                    "max_text_similarity": signal.max_similarity,
                }
            )
            decisions.append(
                SelectionDecision(
                    generation_id=generation_id,
                    submission_id=submission_id,
                    selected=selected,
                    rank=rank_by_id[submission_id],
                    score_vector=vector,
                    reason=reason,
                    selection_kind=kind,
                    novelty_score=signal.novelty_score,
                    redundant_with_submission_id=signal.redundant_with_submission_id,
                )
            )
        return decisions

    def _aggregate(
        self,
        submissions: list[Submission],
        evaluations: list[Evaluation],
    ) -> list[AggregateEvaluation]:
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
        return aggregates

    @staticmethod
    def _quality_key(item: AggregateEvaluation) -> tuple:
        return (
            item.fatal_error,
            -item.correctness,
            -item.rigor,
            -item.research_progress,
            -item.verifiability,
            -item.novelty,
            -item.judge_confidence,
            str(item.submission_id),
        )

    def _diversity_signals(
        self,
        submissions: list[Submission],
        quality_rank: dict[UUID, int],
        redundancy_threshold: float,
    ) -> dict[UUID, DiversitySignal]:
        fingerprints = {
            submission.id: self._fingerprint(submission)
            for submission in submissions
        }
        result: dict[UUID, DiversitySignal] = {}

        for submission in submissions:
            similarities: list[tuple[UUID, float]] = []
            for other in submissions:
                if other.id == submission.id:
                    continue
                similarities.append(
                    (
                        other.id,
                        self._jaccard(
                            fingerprints[submission.id],
                            fingerprints[other.id],
                        ),
                    )
                )

            max_similarity = max((score for _, score in similarities), default=0.0)
            higher_ranked = [
                (other_id, score)
                for other_id, score in similarities
                if quality_rank[other_id] < quality_rank[submission.id]
                and score >= redundancy_threshold
            ]
            higher_ranked.sort(
                key=lambda item: (
                    -item[1],
                    quality_rank[item[0]],
                    str(item[0]),
                )
            )
            redundant_with = higher_ranked[0][0] if higher_ranked else None
            result[submission.id] = DiversitySignal(
                novelty_score=round(1.0 - max_similarity, 6),
                max_similarity=round(max_similarity, 6),
                redundant_with_submission_id=redundant_with,
            )

        return result

    def _redundant_with_selected(
        self,
        submission_id: UUID,
        selected: dict[UUID, SelectionKind],
        submissions: list[Submission],
        redundancy_threshold: float,
    ) -> bool:
        if not selected:
            return False
        by_id = {submission.id: submission for submission in submissions}
        candidate = by_id[submission_id]
        candidate_fp = self._fingerprint(candidate)
        return any(
            self._jaccard(candidate_fp, self._fingerprint(by_id[selected_id]))
            >= redundancy_threshold
            for selected_id in selected
        )

    @staticmethod
    def _fingerprint(submission: Submission) -> frozenset[str]:
        parts = [
            submission.summary,
            submission.approach,
            *submission.evidence,
            *submission.discoveries,
            *submission.failed_attempts,
            *submission.open_questions,
            submission.final_answer or "",
        ]
        for claim in submission.claims:
            parts.extend(
                [
                    claim.statement,
                    claim.support or "",
                ]
            )
        tokens = {
            token
            for token in _TOKEN_RE.findall(" ".join(parts).lower())
            if len(token) > 2 and token not in _STOPWORDS
        }
        return frozenset(tokens)

    @staticmethod
    def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
