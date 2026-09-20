from uuid import uuid4

from packages.core.domain.models import (
    ClaimDraft,
    KnowledgeKind,
    KnowledgeStatus,
    Submission,
)
from packages.core.research.memory import build_memory_packet, extract_knowledge


def test_submission_is_compacted_into_durable_knowledge() -> None:
    submission = Submission(
        agent_id=uuid4(),
        summary="summary",
        approach="Try a spectral decomposition.",
        claims=[
            ClaimDraft(
                statement="The operator is diagonalizable.",
                confidence=0.95,
                support="Distinct eigenvalues.",
            ),
            ClaimDraft(
                statement="A symmetry may reduce the search.",
                confidence=0.55,
            ),
        ],
        discoveries=["The odd case behaves differently."],
        failed_attempts=["Direct enumeration explodes exponentially."],
        open_questions=["Can the symmetry be formalized?"],
        final_answer="Use the decomposition and solve each eigenspace separately.",
    )

    items = extract_knowledge(
        run_id=uuid4(),
        generation_id=uuid4(),
        submission=submission,
    )

    kinds = {item.kind for item in items}
    assert KnowledgeKind.LIKELY_FACT in kinds
    assert KnowledgeKind.HYPOTHESIS in kinds
    assert KnowledgeKind.PROMISING_APPROACH in kinds
    assert KnowledgeKind.OBSERVATION in kinds
    assert KnowledgeKind.FAILED_APPROACH in kinds
    assert KnowledgeKind.UNRESOLVED_QUESTION in kinds
    assert KnowledgeKind.CANDIDATE_SOLUTION in kinds


def test_memory_packet_prefers_verified_and_deduplicates() -> None:
    run_id = uuid4()
    generation_id = uuid4()
    submission_id = uuid4()
    items = extract_knowledge(
        run_id=run_id,
        generation_id=generation_id,
        submission=Submission(
            id=submission_id,
            agent_id=uuid4(),
            summary="summary",
            approach="same approach",
            failed_attempts=["bad path"],
        ),
    )
    duplicate = items[0]
    verified = type(duplicate)(
        run_id=run_id,
        generation_id=generation_id,
        submission_id=submission_id,
        kind=KnowledgeKind.VERIFIED_FACT,
        content="Externally checked fact.",
        status=KnowledgeStatus.VERIFIED,
        confidence=1.0,
    )

    packet = build_memory_packet([*items, duplicate, verified], max_items=3)

    assert packet[0]["kind"] == KnowledgeKind.VERIFIED_FACT.value
    assert len(packet) == 3
