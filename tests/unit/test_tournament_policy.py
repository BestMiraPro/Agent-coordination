from uuid import uuid4

from packages.core.domain.models import Evaluation, Submission
from packages.core.orchestration.tournament_policy import TournamentPolicy


def _submission() -> Submission:
    return Submission(agent_id=uuid4(), summary="candidate", approach="approach")


def _evaluation(
    submission: Submission,
    *,
    correctness: float,
    fatal_error: bool = False,
) -> Evaluation:
    return Evaluation(
        submission_id=submission.id,
        judge_agent_id=uuid4(),
        correctness=correctness,
        rigor=0.8,
        novelty=0.5,
        research_progress=0.7,
        verifiability=0.9,
        fatal_error=fatal_error,
        judge_confidence=0.9,
        critique="test",
    )


def test_selection_is_vector_aware_and_rejects_fatal_branch_first() -> None:
    strong_but_fatal = _submission()
    sound = _submission()
    weaker = _submission()
    fourth = _submission()
    submissions = [strong_but_fatal, sound, weaker, fourth]

    evaluations = [
        _evaluation(strong_but_fatal, correctness=0.99, fatal_error=True),
        _evaluation(strong_but_fatal, correctness=0.99, fatal_error=True),
        _evaluation(sound, correctness=0.91),
        _evaluation(sound, correctness=0.90),
        _evaluation(weaker, correctness=0.75),
        _evaluation(weaker, correctness=0.76),
        _evaluation(fourth, correctness=0.60),
        _evaluation(fourth, correctness=0.61),
    ]

    decisions = TournamentPolicy().select(
        generation_id=uuid4(),
        submissions=submissions,
        evaluations=evaluations,
        survivor_count=2,
    )

    selected = [decision.submission_id for decision in decisions if decision.selected]
    assert sound.id in selected
    assert weaker.id in selected
    assert strong_but_fatal.id not in selected
    assert decisions[-1].submission_id == strong_but_fatal.id


def test_selection_is_deterministic_for_same_inputs() -> None:
    submissions = [_submission() for _ in range(4)]
    evaluations = [
        _evaluation(submission, correctness=0.8)
        for submission in submissions
        for _ in range(2)
    ]
    generation_id = uuid4()
    policy = TournamentPolicy()

    first = policy.select(generation_id, submissions, evaluations, survivor_count=2)
    second = policy.select(generation_id, list(reversed(submissions)), evaluations, survivor_count=2)

    assert [(item.submission_id, item.rank, item.selected) for item in first] == [
        (item.submission_id, item.rank, item.selected) for item in second
    ]
