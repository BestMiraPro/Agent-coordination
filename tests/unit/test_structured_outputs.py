import json

import pytest

from packages.core.structured_outputs import (
    StructuredOutputError,
    parse_judge_output,
    parse_researcher_output,
)


def test_researcher_output_accepts_exact_schema() -> None:
    raw = json.dumps(
        {
            "summary": "A concise result",
            "approach": "Constructive analysis",
            "claims": [
                {
                    "statement": "The key claim",
                    "confidence": 0.8,
                    "support": "Derived directly",
                }
            ],
            "evidence": ["check"],
            "discoveries": ["insight"],
            "failed_attempts": [],
            "open_questions": [],
            "final_answer": "answer",
        }
    )

    parsed = parse_researcher_output(raw)

    assert parsed.summary == "A concise result"
    assert parsed.claims[0].confidence == 0.8


def test_researcher_output_rejects_markdown_fences_and_extra_fields() -> None:
    with pytest.raises(StructuredOutputError):
        parse_researcher_output('''```json
{"summary":"x"}
```''')

    with pytest.raises(StructuredOutputError):
        parse_researcher_output(
            json.dumps(
                {
                    "summary": "x",
                    "approach": "y",
                    "claims": [],
                    "evidence": [],
                    "discoveries": [],
                    "failed_attempts": [],
                    "open_questions": [],
                    "final_answer": None,
                    "unexpected": True,
                }
            )
        )


def test_judge_output_requires_exact_candidate_set() -> None:
    expected = {"candidate_A", "candidate_B"}
    valid = json.dumps(
        {
            "evaluations": [
                {
                    "candidate_id": candidate_id,
                    "correctness": 0.8,
                    "rigor": 0.7,
                    "novelty": 0.6,
                    "research_progress": 0.7,
                    "verifiability": 0.9,
                    "fatal_error": False,
                    "judge_confidence": 0.8,
                    "critique": "reasonable",
                }
                for candidate_id in sorted(expected)
            ]
        }
    )

    parsed = parse_judge_output(valid, expected)
    assert {item.candidate_id for item in parsed.evaluations} == expected

    duplicate = json.loads(valid)
    duplicate["evaluations"][1]["candidate_id"] = "candidate_A"
    with pytest.raises(StructuredOutputError):
        parse_judge_output(json.dumps(duplicate), expected)
