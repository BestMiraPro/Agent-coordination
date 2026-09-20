import pytest

from packages.core.domain.models import RunStatus
from packages.core.orchestration.state_machine import (
    InvalidRunTransition,
    assert_run_transition,
)


def test_valid_run_transition() -> None:
    assert_run_transition(RunStatus.CREATED, RunStatus.RESEARCHING)


def test_invalid_run_transition() -> None:
    with pytest.raises(InvalidRunTransition):
        assert_run_transition(RunStatus.CREATED, RunStatus.COMPLETED)
