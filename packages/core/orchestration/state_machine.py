from __future__ import annotations

from packages.core.domain.models import RunStatus


_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.RESEARCHING, RunStatus.PAUSED, RunStatus.FAILED},
    RunStatus.RESEARCHING: {RunStatus.JUDGING, RunStatus.PAUSED, RunStatus.FAILED},
    RunStatus.JUDGING: {RunStatus.COMPLETED, RunStatus.PAUSED, RunStatus.FAILED},
    RunStatus.PAUSED: {
        RunStatus.RESEARCHING,
        RunStatus.JUDGING,
        RunStatus.FAILED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}


class InvalidRunTransition(ValueError):
    pass


def assert_run_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidRunTransition(f"Invalid run transition: {current} -> {target}")
