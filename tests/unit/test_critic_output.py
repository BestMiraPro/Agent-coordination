import json

from packages.core.structured_outputs import parse_critic_output


def test_critic_output_parses_fatal_counterexample() -> None:
    output = parse_critic_output(
        json.dumps(
            {
                "fatal_error": True,
                "confidence": 0.97,
                "critique": "The universal claim fails at n=2.",
                "counterexample": "n=2",
            }
        )
    )

    assert output.fatal_error is True
    assert output.counterexample == "n=2"
