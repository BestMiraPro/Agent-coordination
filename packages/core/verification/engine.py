from __future__ import annotations

import re
from dataclasses import dataclass

from packages.core.domain.models import (
    CriticFinding,
    Submission,
    VerificationKind,
    VerificationResult,
    VerificationStatus,
)


_PYTHON_BLOCK = re.compile(r"```python\s*(.*?)```", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class VerificationEngine:
    """Deterministic verification layer with task-specific hooks.

    This first implementation verifies structured support, critic survival, and
    Python syntax when executable Python snippets are present. New formal,
    solver, source-retrieval, and sandbox verifiers can be added without
    changing tournament orchestration.
    """

    def verify(
        self,
        *,
        run_id,
        generation_id,
        submission: Submission,
        critic_findings: list[CriticFinding],
    ) -> list[VerificationResult]:
        results = [
            self._verify_adversarial(
                run_id,
                generation_id,
                submission,
                critic_findings,
            ),
            self._verify_structured_evidence(
                run_id,
                generation_id,
                submission,
            ),
        ]
        python_result = self._verify_python(
            run_id,
            generation_id,
            submission,
        )
        if python_result is not None:
            results.append(python_result)
        return results

    @staticmethod
    def overall_status(results: list[VerificationResult]) -> VerificationStatus:
        if any(result.status == VerificationStatus.FAILED for result in results):
            return VerificationStatus.FAILED
        if results and all(
            result.status == VerificationStatus.PASSED for result in results
        ):
            return VerificationStatus.PASSED
        return VerificationStatus.INCONCLUSIVE

    def _verify_adversarial(
        self,
        run_id,
        generation_id,
        submission: Submission,
        findings: list[CriticFinding],
    ) -> VerificationResult:
        relevant = [
            finding for finding in findings if finding.submission_id == submission.id
        ]
        fatal = [finding for finding in relevant if finding.fatal_error]
        if fatal:
            return VerificationResult(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=VerificationKind.ADVERSARIAL_CHECK,
                status=VerificationStatus.FAILED,
                detail="A dedicated critic reported a fatal error.",
                metadata={
                    "critic_finding_ids": [str(item.id) for item in fatal],
                },
            )
        if relevant:
            return VerificationResult(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=VerificationKind.ADVERSARIAL_CHECK,
                status=VerificationStatus.PASSED,
                detail="Configured adversarial critics found no fatal error.",
                metadata={
                    "critic_finding_ids": [str(item.id) for item in relevant],
                },
            )
        return VerificationResult(
            run_id=run_id,
            generation_id=generation_id,
            submission_id=submission.id,
            kind=VerificationKind.ADVERSARIAL_CHECK,
            status=VerificationStatus.INCONCLUSIVE,
            detail="No dedicated critic finding is available.",
        )

    def _verify_structured_evidence(
        self,
        run_id,
        generation_id,
        submission: Submission,
    ) -> VerificationResult:
        if not submission.final_answer or not submission.final_answer.strip():
            return VerificationResult(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=VerificationKind.STRUCTURED_EVIDENCE,
                status=VerificationStatus.INCONCLUSIVE,
                detail="Candidate has no explicit final answer.",
            )

        unsupported = [
            claim.statement
            for claim in submission.claims
            if not claim.support or not claim.support.strip()
        ]
        if unsupported:
            return VerificationResult(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=VerificationKind.STRUCTURED_EVIDENCE,
                status=VerificationStatus.INCONCLUSIVE,
                detail="One or more structured claims lack explicit support.",
                metadata={"unsupported_claims": unsupported[:8]},
            )

        return VerificationResult(
            run_id=run_id,
            generation_id=generation_id,
            submission_id=submission.id,
            kind=VerificationKind.STRUCTURED_EVIDENCE,
            status=VerificationStatus.PASSED,
            detail="Candidate has an explicit answer and all structured claims have support.",
            metadata={
                "claim_count": len(submission.claims),
                "evidence_count": len(submission.evidence),
            },
        )

    def _verify_python(
        self,
        run_id,
        generation_id,
        submission: Submission,
    ) -> VerificationResult | None:
        corpus = "\n".join(
            [
                submission.final_answer or "",
                *submission.evidence,
            ]
        )
        blocks = _PYTHON_BLOCK.findall(corpus)
        if not blocks:
            return None

        errors: list[str] = []
        for index, block in enumerate(blocks):
            try:
                compile(block, f"<candidate-python-{index}>", "exec")
            except SyntaxError as exc:
                errors.append(
                    f"block {index}: {exc.msg} at line {exc.lineno}"
                )

        if errors:
            return VerificationResult(
                run_id=run_id,
                generation_id=generation_id,
                submission_id=submission.id,
                kind=VerificationKind.PYTHON_COMPILE,
                status=VerificationStatus.FAILED,
                detail="Candidate Python snippet failed compilation.",
                metadata={"errors": errors},
            )
        return VerificationResult(
            run_id=run_id,
            generation_id=generation_id,
            submission_id=submission.id,
            kind=VerificationKind.PYTHON_COMPILE,
            status=VerificationStatus.PASSED,
            detail="All candidate Python snippets compile.",
            metadata={"block_count": len(blocks)},
        )
