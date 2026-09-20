from uuid import uuid4

from packages.core.domain.models import (
    ClaimDraft,
    CriticFinding,
    Submission,
    VerificationKind,
    VerificationStatus,
)
from packages.core.verification.engine import VerificationEngine


def test_verification_passes_supported_candidate_and_clean_critic() -> None:
    submission = Submission(
        agent_id=uuid4(),
        summary="candidate",
        approach="direct",
        claims=[
            ClaimDraft(
                statement="supported claim",
                confidence=0.9,
                support="explicit derivation",
            )
        ],
        final_answer="answer",
    )
    critic = CriticFinding(
        generation_id=uuid4(),
        critic_agent_id=uuid4(),
        submission_id=submission.id,
        fatal_error=False,
        confidence=0.9,
        critique="survives",
    )
    engine = VerificationEngine()
    results = engine.verify(
        run_id=uuid4(),
        generation_id=critic.generation_id,
        submission=submission,
        critic_findings=[critic],
    )

    assert engine.overall_status(results) == VerificationStatus.PASSED
    assert {
        result.kind for result in results
    } == {
        VerificationKind.STRUCTURED_EVIDENCE,
        VerificationKind.ADVERSARIAL_CHECK,
    }


def test_python_compile_failure_is_fatal_verification_failure() -> None:
    submission = Submission(
        agent_id=uuid4(),
        summary="code candidate",
        approach="execute",
        claims=[],
        final_answer="answer\n```python\ndef broken(:\n    pass\n```",
    )
    engine = VerificationEngine()
    results = engine.verify(
        run_id=uuid4(),
        generation_id=uuid4(),
        submission=submission,
        critic_findings=[],
    )

    python_result = next(
        result for result in results if result.kind == VerificationKind.PYTHON_COMPILE
    )
    assert python_result.status == VerificationStatus.FAILED
    assert engine.overall_status(results) == VerificationStatus.FAILED
