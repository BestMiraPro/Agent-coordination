from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from packages.core.domain.models import (
    Agent,
    AgentOrigin,
    AgentStatus,
    CrossPollinationKind,
    CrossPollinationPacket,
    Generation,
    JobType,
    LineageLink,
    MutationType,
    ResearchNiche,
    RunEvent,
    RunEventType,
    RunStatus,
    SelectionKind,
)
from packages.core.orchestration.tournament_policy import TournamentPolicy
from packages.core.ports.repositories import JobQueue, UnitOfWork


JUDGE_COUNT = 2
_MUTATION_CYCLE = (
    MutationType.STRENGTHEN,
    MutationType.FALSIFY,
    MutationType.REDERIVE,
    MutationType.GENERALIZE,
)

_NICHE_CYCLE = (
    ResearchNiche.CONSTRUCTIVE,
    ResearchNiche.SKEPTICAL,
    ResearchNiche.COUNTEREXAMPLE,
    ResearchNiche.COMPUTATIONAL,
    ResearchNiche.SPECIAL_CASES,
    ResearchNiche.GENERALIZATION,
    ResearchNiche.ALTERNATIVE_FORMULATION,
    ResearchNiche.LEMMA_DECOMPOSITION,
)


class TournamentOrchestrator:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        queue: JobQueue,
        policy: TournamentPolicy | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.queue = queue
        self.policy = policy or TournamentPolicy()

    def start_run(self, run_id: UUID) -> Generation:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")

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

            researchers = self._ensure_researchers(
                uow,
                run_id,
                generation,
                population_size=run.population_size,
            )

            if run.status == RunStatus.CREATED:
                uow.runs.update_status(run_id, RunStatus.RESEARCHING)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.RUN_STARTED.value,
                        payload={
                            "max_generations": run.max_generations,
                            "population_size": run.population_size,
                            "survivor_count": run.survivor_count,
                            "fresh_agent_count": run.fresh_agent_count,
                            "redundancy_threshold": run.redundancy_threshold,
                        },
                    )
                )
            elif run.status not in {RunStatus.RESEARCHING, RunStatus.JUDGING, RunStatus.COMPLETED}:
                raise RuntimeError(f"Cannot start run from {run.status}")

            uow.commit()

        if run.status != RunStatus.COMPLETED:
            self._enqueue_research_jobs(run_id, generation, researchers)
        return generation

    def maybe_schedule_judging(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> bool:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status != RunStatus.RESEARCHING:
                return False

            generation = self._resolve_generation(uow, run_id, generation_id)
            latest = self._latest_generation(uow, run_id)
            if latest is None or generation.id != latest.id:
                return False

            researchers = self._researchers(uow, generation.id)
            if len(researchers) != run.population_size:
                return False
            if any(agent.status == AgentStatus.FAILED for agent in researchers):
                self.fail_run(run_id, "researcher failed")
                return False
            if not all(agent.status == AgentStatus.COMPLETED for agent in researchers):
                return False
            if len(uow.submissions.list_for_generation(generation.id)) != run.population_size:
                return False

        self.queue.enqueue(
            JobType.START_JUDGING,
            {
                "run_id": str(run_id),
                "generation_id": str(generation.id),
            },
            idempotency_key=f"run:{run_id}:generation:{generation.id}:start-judging",
        )
        return True

    def start_judging(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> list[Agent]:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status == RunStatus.COMPLETED:
                return []
            if run.status not in {RunStatus.RESEARCHING, RunStatus.JUDGING}:
                raise RuntimeError(f"Cannot start judging from {run.status}")

            generation = self._resolve_generation(uow, run_id, generation_id)
            latest = self._latest_generation(uow, run_id)
            if latest is None or generation.id != latest.id:
                return []

            researchers = self._researchers(uow, generation.id)
            submissions = uow.submissions.list_for_generation(generation.id)
            if (
                len(researchers) != run.population_size
                or not all(agent.status == AgentStatus.COMPLETED for agent in researchers)
                or len(submissions) != run.population_size
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
                            payload={
                                "agent_id": str(agent.id),
                                "role": agent.role,
                                "generation_id": str(generation.id),
                            },
                        )
                    )

            if run.status == RunStatus.RESEARCHING:
                uow.runs.update_status(run_id, RunStatus.JUDGING)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.JUDGING_STARTED.value,
                        payload={
                            "generation_id": str(generation.id),
                            "index": generation.index,
                        },
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
                idempotency_key=f"run:{run_id}:generation:{generation.id}:judge:{judge.id}",
            )
        return judges

    def maybe_schedule_finalize(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> bool:
        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            if run.status != RunStatus.JUDGING:
                return run.status == RunStatus.COMPLETED

            generation = self._resolve_generation(uow, run_id, generation_id)
            latest = self._latest_generation(uow, run_id)
            if latest is None or generation.id != latest.id:
                return False

            judges = self._judges(uow, generation.id)
            if len(judges) != JUDGE_COUNT:
                return False
            if any(agent.status == AgentStatus.FAILED for agent in judges):
                self.fail_run(run_id, "judge failed")
                return False
            if not all(agent.status == AgentStatus.COMPLETED for agent in judges):
                return False
            if not self._evaluations_complete(uow, generation.id, judges):
                return False

        self.queue.enqueue(
            JobType.FINALIZE_RUN,
            {
                "run_id": str(run_id),
                "generation_id": str(generation.id),
            },
            idempotency_key=f"run:{run_id}:generation:{generation.id}:finalize",
        )
        return True

    def finalize_run(
        self,
        run_id: UUID,
        generation_id: UUID | None = None,
    ) -> None:
        enqueue: tuple[Generation, list[Agent]] | None = None

        with self.uow_factory() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise KeyError(f"Run not found: {run_id}")
            generation = self._resolve_generation(uow, run_id, generation_id)
            if run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                return
            latest = self._latest_generation(uow, run_id)

            if latest is not None and latest.index > generation.index:
                researchers = self._researchers(uow, latest.id)
                enqueue = (latest, researchers)
                uow.commit()
            else:
                judges = self._judges(uow, generation.id)
                if (
                    run.status != RunStatus.JUDGING
                    or len(judges) != JUDGE_COUNT
                    or not all(agent.status == AgentStatus.COMPLETED for agent in judges)
                    or not self._evaluations_complete(uow, generation.id, judges)
                ):
                    raise RuntimeError("Run cannot advance before judging is complete")

                if generation.index + 1 >= run.max_generations:
                    uow.runs.update_status(run_id, RunStatus.COMPLETED)
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.RUN_COMPLETED.value,
                            payload={
                                "generation_id": str(generation.id),
                                "generation_index": generation.index,
                            },
                        )
                    )
                    uow.commit()
                    return

                decisions = uow.selections.list_for_generation(generation.id)
                if not decisions:
                    submissions = uow.submissions.list_for_generation(generation.id)
                    evaluations = uow.evaluations.list_for_generation(generation.id)
                    decisions = self.policy.select(
                        generation_id=generation.id,
                        submissions=submissions,
                        evaluations=evaluations,
                        survivor_count=run.survivor_count,
                        redundancy_threshold=run.redundancy_threshold,
                    )
                    uow.selections.add_many(decisions)
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.DIVERSITY_ANALYZED.value,
                            payload={
                                "generation_id": str(generation.id),
                                "redundancy_threshold": run.redundancy_threshold,
                                "redundant_count": sum(
                                    item.redundant_with_submission_id is not None
                                    for item in decisions
                                ),
                                "mean_novelty": (
                                    sum(item.novelty_score for item in decisions)
                                    / len(decisions)
                                ),
                            },
                        )
                    )
                    for decision in decisions:
                        if decision.redundant_with_submission_id is not None:
                            uow.events.append(
                                RunEvent(
                                    run_id=run_id,
                                    event_type=RunEventType.REDUNDANCY_DETECTED.value,
                                    payload={
                                        "generation_id": str(generation.id),
                                        "submission_id": str(decision.submission_id),
                                        "redundant_with_submission_id": str(
                                            decision.redundant_with_submission_id
                                        ),
                                        "novelty_score": decision.novelty_score,
                                    },
                                )
                            )
                        if (
                            decision.selected
                            and decision.selection_kind == SelectionKind.WILDCARD
                        ):
                            uow.events.append(
                                RunEvent(
                                    run_id=run_id,
                                    event_type=RunEventType.WILDCARD_SELECTED.value,
                                    payload={
                                        "generation_id": str(generation.id),
                                        "submission_id": str(decision.submission_id),
                                        "rank": decision.rank,
                                    },
                                )
                            )
                        uow.events.append(
                            RunEvent(
                                run_id=run_id,
                                event_type=(
                                    RunEventType.BRANCH_SELECTED.value
                                    if decision.selected
                                    else RunEventType.BRANCH_ELIMINATED.value
                                ),
                                payload={
                                    "generation_id": str(generation.id),
                                    "submission_id": str(decision.submission_id),
                                    "rank": decision.rank,
                                    "score_vector": decision.score_vector,
                                    "selection_kind": decision.selection_kind.value,
                                    "novelty_score": decision.novelty_score,
                                    "redundant_with_submission_id": (
                                        str(decision.redundant_with_submission_id)
                                        if decision.redundant_with_submission_id
                                        else None
                                    ),
                                },
                            )
                        )
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.SELECTION_COMPLETED.value,
                            payload={
                                "generation_id": str(generation.id),
                                "selected": sum(item.selected for item in decisions),
                                "population": len(decisions),
                            },
                        )
                    )

                selected = sorted(
                    (item for item in decisions if item.selected),
                    key=lambda item: item.rank,
                )
                if not selected:
                    raise RuntimeError("Selection produced no survivors")

                next_index = generation.index + 1
                next_generation = uow.generations.get_for_run(run_id, next_index)
                if next_generation is None:
                    next_generation = uow.generations.add(
                        Generation(run_id=run_id, index=next_index)
                    )
                    uow.events.append(
                        RunEvent(
                            run_id=run_id,
                            event_type=RunEventType.GENERATION_CREATED.value,
                            payload={
                                "generation_id": str(next_generation.id),
                                "index": next_index,
                            },
                        )
                    )

                researchers = self._researchers(uow, next_generation.id)
                if not researchers:
                    clone_count = run.population_size - run.fresh_agent_count
                    children = [
                        Agent(
                            generation_id=next_generation.id,
                            role=f"researcher:{index}",
                            niche=_NICHE_CYCLE[
                                (next_generation.index + index) % len(_NICHE_CYCLE)
                            ],
                            origin=(
                                AgentOrigin.CLONED
                                if index < clone_count
                                else AgentOrigin.FRESH
                            ),
                        )
                        for index in range(run.population_size)
                    ]
                    researchers = uow.agents.add_many(children)

                    lineage_links: list[LineageLink] = []
                    cross_packets: list[CrossPollinationPacket] = []
                    for index, child in enumerate(researchers):
                        uow.events.append(
                            RunEvent(
                                run_id=run_id,
                                event_type=RunEventType.AGENT_SPAWNED.value,
                                payload={
                                    "agent_id": str(child.id),
                                    "role": child.role,
                                    "generation_id": str(next_generation.id),
                                    "niche": child.niche.value,
                                    "origin": child.origin.value,
                                },
                            )
                        )
                        if child.origin == AgentOrigin.FRESH:
                            uow.events.append(
                                RunEvent(
                                    run_id=run_id,
                                    event_type=RunEventType.FRESH_AGENT_INJECTED.value,
                                    payload={
                                        "agent_id": str(child.id),
                                        "generation_id": str(next_generation.id),
                                        "niche": child.niche.value,
                                    },
                                )
                            )
                            continue

                        parent = selected[index % len(selected)]
                        mutation = _MUTATION_CYCLE[index % len(_MUTATION_CYCLE)]
                        lineage_links.append(
                            LineageLink(
                                child_agent_id=child.id,
                                parent_submission_id=parent.submission_id,
                                mutation_type=mutation,
                            )
                        )

                        if len(selected) > 1:
                            source = selected[(index + 1) % len(selected)]
                            if source.submission_id != parent.submission_id:
                                source_submission = uow.submissions.get(source.submission_id)
                                if source_submission is not None:
                                    packet_kind = (
                                        CrossPollinationKind.TRY
                                        if source.selection_kind
                                        in {SelectionKind.NOVELTY, SelectionKind.WILDCARD}
                                        else CrossPollinationKind.PROMISING
                                    )
                                    packet = CrossPollinationPacket(
                                        run_id=run_id,
                                        generation_id=next_generation.id,
                                        target_agent_id=child.id,
                                        source_submission_id=source_submission.id,
                                        kind=packet_kind,
                                        payload={
                                            "summary": source_submission.summary,
                                            "approach": source_submission.approach,
                                            "discoveries": source_submission.discoveries[:3],
                                            "open_questions": source_submission.open_questions[:3],
                                        },
                                    )
                                    cross_packets.append(packet)
                                    uow.events.append(
                                        RunEvent(
                                            run_id=run_id,
                                            event_type=RunEventType.CROSS_POLLINATION_CREATED.value,
                                            payload={
                                                "packet_id": str(packet.id),
                                                "target_agent_id": str(child.id),
                                                "source_submission_id": str(
                                                    source_submission.id
                                                ),
                                                "kind": packet_kind.value,
                                                "generation_id": str(next_generation.id),
                                            },
                                        )
                                    )
                        uow.events.append(
                            RunEvent(
                                run_id=run_id,
                                event_type=RunEventType.AGENT_CLONED.value,
                                payload={
                                    "child_agent_id": str(child.id),
                                    "parent_submission_id": str(parent.submission_id),
                                    "mutation_type": mutation.value,
                                    "generation_id": str(next_generation.id),
                                    "niche": child.niche.value,
                                },
                            )
                        )
                    if lineage_links:
                        uow.lineages.add_many(lineage_links)
                    if cross_packets:
                        uow.cross_pollination.add_many(cross_packets)

                uow.runs.update_status(run_id, RunStatus.RESEARCHING)
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.GENERATION_ADVANCED.value,
                        payload={
                            "from_generation_id": str(generation.id),
                            "to_generation_id": str(next_generation.id),
                            "to_index": next_generation.index,
                        },
                    )
                )
                uow.commit()
                enqueue = (next_generation, researchers)

        if enqueue is not None:
            next_generation, researchers = enqueue
            self._enqueue_research_jobs(run_id, next_generation, researchers)

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

    def _ensure_researchers(
        self,
        uow: UnitOfWork,
        run_id: UUID,
        generation: Generation,
        population_size: int,
    ) -> list[Agent]:
        existing = {
            agent.role: agent
            for agent in self._researchers(uow, generation.id)
        }
        missing = [
            Agent(
                generation_id=generation.id,
                role=f"researcher:{index}",
                niche=_NICHE_CYCLE[
                    (generation.index + index) % len(_NICHE_CYCLE)
                ],
                origin=AgentOrigin.INITIAL,
            )
            for index in range(population_size)
            if f"researcher:{index}" not in existing
        ]
        if missing:
            for agent in uow.agents.add_many(missing):
                existing[agent.role] = agent
                uow.events.append(
                    RunEvent(
                        run_id=run_id,
                        event_type=RunEventType.AGENT_SPAWNED.value,
                        payload={
                            "agent_id": str(agent.id),
                            "role": agent.role,
                            "generation_id": str(generation.id),
                            "niche": agent.niche.value,
                            "origin": agent.origin.value,
                        },
                    )
                )
        return [existing[f"researcher:{index}"] for index in range(population_size)]

    def _enqueue_research_jobs(
        self,
        run_id: UUID,
        generation: Generation,
        researchers: list[Agent],
    ) -> None:
        for agent in researchers:
            self.queue.enqueue(
                JobType.RUN_RESEARCH_AGENT,
                {
                    "run_id": str(run_id),
                    "generation_id": str(generation.id),
                    "agent_id": str(agent.id),
                },
                idempotency_key=(
                    f"run:{run_id}:generation:{generation.id}:research:{agent.id}"
                ),
            )

    @staticmethod
    def _latest_generation(uow: UnitOfWork, run_id: UUID) -> Generation | None:
        generations = uow.generations.list_for_run(run_id)
        return generations[-1] if generations else None

    @staticmethod
    def _resolve_generation(
        uow: UnitOfWork,
        run_id: UUID,
        generation_id: UUID | None,
    ) -> Generation:
        if generation_id is not None:
            generation = uow.generations.get(generation_id)
            if generation is None or generation.run_id != run_id:
                raise KeyError(f"Generation not found for run: {generation_id}")
            return generation
        generations = uow.generations.list_for_run(run_id)
        if not generations:
            raise RuntimeError("Run has no generations")
        return generations[-1]

    @staticmethod
    def _researchers(uow: UnitOfWork, generation_id: UUID) -> list[Agent]:
        return [
            agent
            for agent in uow.agents.list_for_generation(generation_id)
            if agent.role.startswith("researcher:")
        ]

    @staticmethod
    def _judges(uow: UnitOfWork, generation_id: UUID) -> list[Agent]:
        return [
            agent
            for agent in uow.agents.list_for_generation(generation_id)
            if agent.role.startswith("judge:")
        ]

    @staticmethod
    def _evaluations_complete(
        uow: UnitOfWork,
        generation_id: UUID,
        judges: list[Agent],
    ) -> bool:
        submissions = uow.submissions.list_for_generation(generation_id)
        evaluations = uow.evaluations.list_for_generation(generation_id)
        expected = {
            (submission.id, judge.id)
            for submission in submissions
            for judge in judges
        }
        actual = {
            (evaluation.submission_id, evaluation.judge_agent_id)
            for evaluation in evaluations
        }
        return bool(submissions) and actual == expected
