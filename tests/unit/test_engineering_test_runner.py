from uuid import uuid4

from packages.core.engineering.testing import EngineeringTestRunner


def test_engineering_test_runner_rejects_unsafe_and_invalid_python() -> None:
    runner = EngineeringTestRunner()
    checks = runner.run(
        engineering_run_id=uuid4(),
        repair_cycle=0,
        implementation_payloads=[
            {
                "files": [
                    {"path": "../escape.py", "content": "def broken(:\n pass"},
                    {"path": "tests/test_ok.py", "content": "def test_ok():\n    assert True\n"},
                ]
            }
        ],
    )
    by_name = {check.name: check for check in checks}

    assert by_name["safe_paths"].passed is False
    assert by_name["python_compile"].passed is False
    assert by_name["test_artifact_present"].passed is True
