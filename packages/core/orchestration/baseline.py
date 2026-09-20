from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from string import ascii_uppercase
from uuid import UUID

from packages.core.domain.models import (
    Agent,
    AgentStatus,
    Generation,
    JobType,
    RunEvent,
    RunEventType,
    RunStatus,
    Submission,
)
from packages.core.ports.repositories import JobQueue, UnitOfWork


RESEARCHER_COUNT = 4
JUDGE_COUNT = 2


@dataclass(frozen=True, slots=True)
class BlindedSubmission:
    candidate_id: str
    submission: Submission


def blind_submissions(
    submissions: list[Submission],
    judge_agent_id: UUID,
) -> list[BlindedSubmission]:
    if len(submissions) > len(ascii_uppercase):
        raise ValueError("Too many submissions for Phase 1 blind labels")

    ordered = sorted(
        submissions,
        key=lambda submission: sha256(
            f"{judge_agent_id}:{submission.id}".encode()
        ).digest(),
    )
    return [
        BlindedSubmission(
            candidate_id=f"candidate_{ascii_uppercase[index]}",
            submission=submission,
        )
        for index, submission in enumerate(ordered)
    ]


class BaselineOrchestrator:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        queue: JobQueue,
    ) -> None:
        self.uow_factory = uow_factory
        self.queue = queue

    def start_run(self, run_id: UUID) -> Generation:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")

            if run.status not in {RunStatus.CREATED, RunStatus.RESEARCHING}:
                generation = uow.generations.get_for_run(run_id, 0)
                if generation is None:
                    raise RuntimeError("Run advanced without Generation 0")
                return generation

            generation = uow.generations.get_for_run(run_id, 0)
            if generation is None:
                generation = uow.generations.add(Generation(run_id=run_id, index=0))
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.GENERATION_CREATED.value,
                        payload={"generation_id": str(generation.id), "index": 0},
                    )
                )

            existing = {
                agent.role: agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("researcher:")
            }
            missing = [
                Agent(generation_id=generation.id, role=f"researcher:{index}")
                for index in range(RESEARCHER_COUNT)
                if f"researcher:{index}" not in existing
            ]
            if missing:
                for agent in uow.agents.add_many(missing):
                    existing[agent.role] = agent
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.AGENT_SPAWNED.value,
                            payload={"agent_id": str(agent.id), "role": agent.role},
                        )
                    )

            if run.status == RunStatus.CREATED:
                uow.runs.update_status(run_id, RunStatus.RESEARCHING)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.RUN_STARTED.value,
                        payload={},
                    )
                )

            uow.commit()
            researchers = [existing[f"researcher:{index}"] for index in range(RESEARCHER_COUNT)]

        for agent in researchers:
            self.queue.enqueue(
                JobType.RUN_RESEARCH_AGENT,
                {
                    "run_id": str(run_id),
                    "generation_id": str(generation.id),
                    "agent_id": str(agent.id),
                },
                idempotency_key=f"run:{run_id}:research:{agent.id}",
            )
        return generation

    def maybe_schedule_judging(self, run_id: UUID) -> bool:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status != RunStatus.RESEARCHING:
                return run.status in {RunStatus.JUDGING, RunStatus.COMPLETED}

            generation = uow.generations.get_for_run(run_id, 0)
            if generation is None:
                return False

            researchers = [
                agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("researcher:")
            ]
            if len(researchers) != RESEARCHER_COUNT:
                return False
            if any(agent.status == AgentStatus.FAILED for agent in researchers):
                self.fail_run(run_id, "researcher failed")
                return False
            if not all(agent.status == AgentStatus.COMPLETED for agent in researchers):
                return False
            if len(uow.submissions.list_for_generation(generation.id)) != RESEARCHER_COUNT:
                return False

        self.queue.enqueue(
            JobType.START_JUDGING,
            {"run_id": str(run_id)},
            idempotency_key=f"run:{run_id}:start-judging",
        )
        return True

    def start_judging(self, run_id: UUID) -> list[Agent]:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status == RunStatus.COMPLETED:
                return []
            if run.status not in {RunStatus.RESEARCHING, RunStatus.JUDGING}:
                raise RuntimeError(f"Cannot start judging from {run.status}")

            generation = uow.generations.get_for_run(run_id, 0)
            if generation is None:
                raise RuntimeError("Generation 0 is missing")

            researchers = [
                agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("researcher:")
            ]
            submissions = uow.submissions.list_for_generation(generation.id)
            if (
                len(researchers) != RESEARCHER_COUNT
                or not all(agent.status == AgentStatus.COMPLETED for agent in researchers)
                or len(submissions) != RESEARCHER_COUNT
            ):
                raise RuntimeError("Research phase is not complete")

            existing = {
                agent.role: agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("judge:")
            }
            missing = [
                Agent(generation_id=generation.id, role=f"judge:{index}")
                for index in range(JUDGE_COUNT)
                if f"judge:{index}" not in existing
            ]
            if missing:
                for agent in uow.agents.add_many(missing):
                    existing[agent.role] = agent
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.AGENT_SPAWNED.value,
                            payload={"agent_id": str(agent.id), "role": agent.role},
                        )
                    )

            if run.status == RunStatus.RESEARCHING:
                uow.runs.update_status(run_id, RunStatus.JUDGING)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.JUDGING_STARTED.value,
                        payload={},
                    )
                )

            uow.commit()
            judges = [existing[f"judge:{index}"] for index in range(JUDGE_COUNT)]

        for judge in judges:
            self.queue.enqueue(
                JobType.RUN_JUDGE,
                {
                    "run_id": str(run_id),
                    "generation_id": str(generation.id),
                    "agent_id": str(judge.id),
                },
                idempotency_key=f"run:{run_id}:judge:{judge.id}",
            )
        return judges

    def maybe_schedule_finalize(self, run_id: UUID) -> bool:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status != RunStatus.JUDGING:
                return run.status == RunStatus.COMPLETED

            generation = uow.generations.get_for_run(run_id, 0)
            if generation is None:
                return False
            judges = [
                agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("judge:")
            ]
            if len(judges) != JUDGE_COUNT:
                return False
            if any(agent.status == AgentStatus.FAILED for agent in judges):
                self.fail_run(run_id, "judge failed")
                return False
            if not all(agent.status == AgentStatus.COMPLETED for agent in judges):
                return False

            submissions = uow.submissions.list_for_generation(generation.id)
            evaluations = uow.evaluations.list_for_generation(generation.id)
            expected_pairs = {
                (submission.id, judge.id)
                for submission in submissions
                for judge in judges
            }
            actual_pairs = {
                (evaluation.submission_id, evaluation.judge_agent_id)
                for evaluation in evaluations
            }
            if actual_pairs != expected_pairs:
                return False

        self.queue.enqueue(
            JobType.FINALIZE_RUN,
            {"run_id": str(run_id)},
            idempotency_key=f"run:{run_id}:finalize",
        )
        return True

    def finalize_run(self, run_id: UUID) -> None:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status == RunStatus.COMPLETED:
                return
            if run.status != RunStatus.JUDGING:
                raise RuntimeError(f"Cannot finalize from {run.status}")

            generation = uow.generations.get_for_run(run_id, 0)
            if generation is None:
                raise RuntimeError("Generation 0 is missing")
            submissions = uow.submissions.list_for_generation(generation.id)
            judges = [
                agent
                for agent in uow.agents.list_for_generation(generation.id)
                if agent.role.startswith("judge:")
            ]
            evaluations = uow.evaluations.list_for_generation(generation.id)
            expected_pairs = {
                (submission.id, judge.id)
                for submission in submissions
                for judge in judges
            }
            actual_pairs = {
                (evaluation.submission_id, evaluation.judge_agent_id)
                for evaluation in evaluations
            }
            if (
                len(submissions) != RESEARCHER_COUNT
                or len(judges) != JUDGE_COUNT
                or not all(agent.status == AgentStatus.COMPLETED for agent in judges)
                or actual_pairs != expected_pairs
            ):
                raise RuntimeError("Run cannot be finalized before judging is complete")

            uow.runs.update_status(run_id, RunStatus.COMPLETED)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.RUN_COMPLETED.value,
                    payload={},
                )
            )
            uow.commit()

    def fail_run(self, run_id: UUID, reason: str, agent_id: UUID | None = None) -> None:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                return

            if agent_id is not None:
                agent = uow.agents.get(agent_id)
                if agent is not None and agent.status != AgentStatus.FAILED:
                    uow.agents.update_status(agent_id, AgentStatus.FAILED)
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.AGENT_FAILED.value,
                            payload={"agent_id": str(agent_id), "reason": reason},
                        )
                    )

            uow.runs.update_status(run_id, RunStatus.FAILED)
            uow.events.append(
                RunEvent(
                    run_id=run_id,
                    event_type=RunEventType.RUN_FAILED.value,
                    payload={"reason": reason},
                )
            )
            uow.commit()
