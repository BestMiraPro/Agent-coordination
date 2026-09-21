from __future__ import annotations

import re
from collections.abc import Iterable

from packages.core.domain.models import (
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    Submission,
)

_WHITESPACE = re.compile(r"\s+")
_KIND_PRIORITY = {
    KnowledgeKind.VERIFIED_FACT: 0,
    KnowledgeKind.COUNTEREXAMPLE: 1,
    KnowledgeKind.CONTRADICTION: 2,
    KnowledgeKind.CANDIDATE_LEMMA: 3,
    KnowledgeKind.LIKELY_FACT: 4,
    KnowledgeKind.PROMISING_APPROACH: 5,
    KnowledgeKind.OBSERVATION: 6,
    KnowledgeKind.HYPOTHESIS: 7,
    KnowledgeKind.FAILED_APPROACH: 8,
    KnowledgeKind.UNRESOLVED_QUESTION: 9,
    KnowledgeKind.CANDIDATE_SOLUTION: 10,
}


def extract_knowledge(
    *,
    run_id,
    generation_id,
    submission: Submission,
) -> list[KnowledgeItem]:
    items: list[KnowledgeItem] = []

    for claim in submission.claims:
        confidence = claim.confidence
        if confidence is not None and confidence >= 0.9 and claim.support:
            kind = KnowledgeKind.LIKELY_FACT
        elif claim.support and confidence is not None and confidence >= 0.7:
            kind = KnowledgeKind.CANDIDATE_LEMMA
        else:
            kind = KnowledgeKind.HYPOTHESIS
        items.append(
            KnowledgeItem(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=kind,
                content=claim.statement,
                confidence=confidence,
                provenance={
                    "support": claim.support,
                    "source": "researcher_claim",
                },
            )
        )

    if submission.approach.strip():
        items.append(
            KnowledgeItem(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=KnowledgeKind.PROMISING_APPROACH,
                content=submission.approach.strip(),
                provenance={"source": "researcher_approach"},
            )
        )

    for discovery in submission.discoveries:
        if discovery.strip():
            items.append(
                KnowledgeItem(
                    run_id=run_id,
                    generation_id=generation_id,
                    submission_id=submission.id,
                    kind=KnowledgeKind.OBSERVATION,
                    content=discovery.strip(),
                    provenance={"source": "researcher_discovery"},
                )
            )

    for failed in submission.failed_attempts:
        if failed.strip():
            items.append(
                KnowledgeItem(
                    run_id=run_id,
                    generation_id=generation_id,
                    submission_id=submission.id,
                    kind=KnowledgeKind.FAILED_APPROACH,
                    content=failed.strip(),
                    provenance={"source": "researcher_failed_attempt"},
                )
            )

    for question in submission.open_questions:
        if question.strip():
            items.append(
                KnowledgeItem(
                    run_id=run_id,
                    generation_id=generation_id,
                    submission_id=submission.id,
                    kind=KnowledgeKind.UNRESOLVED_QUESTION,
                    content=question.strip(),
                    provenance={"source": "researcher_open_question"},
                )
            )

    if submission.final_answer and submission.final_answer.strip():
        items.append(
            KnowledgeItem(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=KnowledgeKind.CANDIDATE_SOLUTION,
                content=submission.final_answer.strip(),
                provenance={"source": "researcher_final_answer"},
            )
        )

    return _dedupe(items)


def build_memory_packet(
    items: Iterable[KnowledgeItem],
    *,
    max_items: int = 12,
) -> list[dict[str, object]]:
    if max_items <= 0:
        return []

    usable = [
        item
        for item in items
        if item.status != KnowledgeStatus.REFUTED and item.content.strip()
    ]
    usable.sort(
        key=lambda item: (
            0 if item.status == KnowledgeStatus.VERIFIED else 1,
            _KIND_PRIORITY[item.kind],
            -(item.confidence if item.confidence is not None else 0.0),
            str(item.id),
        )
    )

    packet: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in usable:
        key = _normalize(item.content)
        if key in seen:
            continue
        seen.add(key)
        packet.append(
            {
                "kind": item.kind.value,
                "status": item.status.value,
                "content": item.content,
                "confidence": item.confidence,
                "provenance": item.provenance,
            }
        )
        if len(packet) >= max_items:
            break
    return packet


def _dedupe(items: Iterable[KnowledgeItem]) -> list[KnowledgeItem]:
    seen: set[tuple[KnowledgeKind, str]] = set()
    result: list[KnowledgeItem] = []
    for item in items:
        key = (item.kind, _normalize(item.content))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _normalize(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip().lower())
