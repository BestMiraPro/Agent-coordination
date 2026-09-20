from uuid import uuid4

from packages.core.domain.models import Submission
from packages.core.orchestration.baseline import blind_submissions


def test_blinding_is_deterministic_and_assigns_opaque_labels() -> None:
    submissions = [
        Submission(
            agent_id=uuid4(),
            summary=f"summary {index}",
            approach="approach",
        )
        for index in range(4)
    ]
    judge_id = uuid4()

    first = blind_submissions(submissions, judge_id)
    second = blind_submissions(list(reversed(submissions)), judge_id)

    assert [item.submission.id for item in first] == [
        item.submission.id for item in second
    ]
    assert [item.candidate_id for item in first] == [
        "candidate_A",
        "candidate_B",
        "candidate_C",
        "candidate_D",
    ]
