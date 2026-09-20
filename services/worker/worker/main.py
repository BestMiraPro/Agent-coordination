from __future__ import annotations

import asyncio

from packages.core.domain.models import ModelProfile, ModelState
from packages.core.engineering.orchestration import EngineeringOrchestrator
from packages.core.orchestration.tournament import TournamentOrchestrator
from packages.persistence.database import build_engine, build_session_factory
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from packages.providers.base import ModelProvider
from packages.providers.fake import PhaseOneFakeProvider
from packages.providers.openai_compatible import OpenAICompatibleProvider
from packages.providers.routed import AdaptiveProvider, ProviderRoute
from services.worker.worker.handlers.baseline import BaselineJobHandler
from services.worker.worker.handlers.engineering import (
    CompositeJobHandler,
    EngineeringJobHandler,
)
from services.worker.worker.runtime import run_once, run_worker
from services.worker.worker.settings import WorkerSettings


def build_provider(settings: WorkerSettings) -> tuple[ModelProvider, str, str, dict[str, object]]:
    if settings.inference_provider == "fake":
        return (
            PhaseOneFakeProvider(),
            "fake",
            "fake/phase-one",
            {"mode": "deterministic"},
        )

    secret = settings.inference_api_key
    if secret is None or not secret.get_secret_value():
        raise RuntimeError(
            "INFERENCE_API_KEY is required when INFERENCE_PROVIDER is not fake"
        )

    provider_name = settings.inference_provider
    return (
        OpenAICompatibleProvider(
            base_url=settings.inference_base_url,
            api_key=secret.get_secret_value(),
            provider_name=provider_name,
            project=settings.inference_project,
            supports_json_schema=settings.inference_structured_outputs,
        ),
        provider_name,
        settings.inference_model,
        {
            "base_url": settings.inference_base_url,
            "project": settings.inference_project,
            "structured_outputs": settings.inference_structured_outputs,
        },
    )


def build_handler(
    settings: WorkerSettings | None = None,
) -> tuple[DurableJobQueue, CompositeJobHandler, WorkerSettings]:
    settings = settings or WorkerSettings()
    engine = build_engine()
    session_factory = build_session_factory(engine)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    provider, provider_name, model_name, metadata = build_provider(settings)

    with uow_factory() as uow:
        profile = uow.model_profiles.find(provider_name, model_name)
        if profile is None:
            profile = uow.model_profiles.add(
                ModelProfile(
                    provider=provider_name,
                    model=model_name,
                    metadata=metadata,
                )
            )
        state = uow.model_states.get_for_profile(profile.id)
        if state is None:
            state = uow.model_states.add(
                ModelState(
                    model_profile_id=profile.id,
                    quality_by_task={
                        "default": 0.7,
                        "research": 0.72,
                        "judge": 0.7,
                        "critic": 0.7,
                    },
                    marginal_cash_cost=0.0,
                    credit_cost=0.0,
                    latency_ms=1000.0,
                    scarcity=0.0,
                    failure_rate=0.0,
                    rate_limit_pressure=0.0,
                    available_concurrency=1,
                )
            )
        uow.commit()

    provider = AdaptiveProvider(
        [
            ProviderRoute(
                model_profile_id=profile.id,
                model_name=profile.model,
                provider=provider,
                state=state,
            )
        ]
    )

    queue = DurableJobQueue(session_factory, worker_id=settings.worker_id)
    orchestrator = TournamentOrchestrator(uow_factory, queue)
    research_handler = BaselineJobHandler(
        uow_factory=uow_factory,
        orchestrator=orchestrator,
        provider=provider,
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )
    engineering_orchestrator = EngineeringOrchestrator(uow_factory, queue)
    engineering_handler = EngineeringJobHandler(
        uow_factory=uow_factory,
        orchestrator=engineering_orchestrator,
        provider=provider,
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )
    handler = CompositeJobHandler(research_handler, engineering_handler)
    return queue, handler, settings


async def main() -> None:
    queue, handler, settings = build_handler()
    await run_worker(
        queue,
        handler,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
    )


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ["build_handler", "build_provider", "main", "run_once", "run_worker"]
