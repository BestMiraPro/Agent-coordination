from uuid import uuid4

from packages.core.domain.models import Evaluation, Submission
from packages.core.orchestration.tournament_policy import TournamentPolicy


def _submission(label: str, approach: str) -> Submission:
    return Submission(
        agent_id=uuid4(),
        summary=label,
        approach=approach,
        discoveries=[f"discovery from {label}"],
    )


def _eval(submission: Submission, correctness: float) -> Evaluation:
    return Evaluation(
        submission_id=submission.id,
        judge_agent_id=uuid4(),
        correctness=correctness,
        rigor=0.8,
        novelty=0.5,
        research_progress=0.75,
        verifiability=0.8,
        fatal_error=False,
        judge_confidence=0.9,
        critique="benchmark",
    )


def test_diversity_policy_resists_premature_convergence_better_than_top_k() -> None:
    dominant = [
        _submission(
            f"dominant-{index}",
            "Use the same spectral relaxation and eigenvalue bound for the proof.",
        )
        for index in range(3)
    ]
    alternatives = [
        _submission(
            "counterexample",
            "Search minimal counterexamples by exhaustive finite enumeration.",
        ),
        _submission(
            "combinatorial",
            "Construct an injection and prove the counting identity bijectively.",
        ),
        _submission(
            "geometric",
            "Translate the constraints into convex geometry and use separation.",
        ),
    ]
    submissions = dominant + alternatives

    correctness = {
        dominant[0].id: 0.96,
        dominant[1].id: 0.95,
        dominant[2].id: 0.94,
        alternatives[0].id: 0.86,
        alternatives[1].id: 0.84,
        alternatives[2].id: 0.82,
    }
    evaluations = [
        _eval(submission, correctness[submission.id])
        for submission in submissions
        for _ in range(2)
    ]

    top_k = sorted(
        submissions,
        key=lambda item: -correctness[item.id],
    )[:3]
    top_k_alternative_count = sum(item in alternatives for item in top_k)

    decisions = TournamentPolicy().select(
        generation_id=uuid4(),
        submissions=submissions,
        evaluations=evaluations,
        survivor_count=3,
        redundancy_threshold=0.7,
    )
    selected_ids = {
        decision.submission_id
        for decision in decisions
        if decision.selected
    }
    diversity_alternative_count = sum(
        submission.id in selected_ids
        for submission in alternatives
    )

    assert top_k_alternative_count == 0
    assert diversity_alternative_count >= 1
    assert diversity_alternative_count > top_k_alternative_count
