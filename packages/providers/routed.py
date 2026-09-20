from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from packages.core.domain.models import ModelState
from packages.core.routing.adaptive import AdaptiveRouter
from packages.providers.base import ModelProvider, ModelRequest, ModelResponse


@dataclass(slots=True)
class ProviderRoute:
    model_profile_id: UUID
    model_name: str
    provider: ModelProvider
    state: ModelState


class AdaptiveProvider:
    """ModelProvider wrapper that routes each task before invoking inference."""

    def __init__(
        self,
        routes: list[ProviderRoute],
        router: AdaptiveRouter | None = None,
    ) -> None:
        if not routes:
            raise ValueError("AdaptiveProvider requires at least one route")
        self.routes = routes
        self.router = router or AdaptiveRouter()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        decision = self.router.choose(
            request.task_type,
            [route.state for route in self.routes],
            task_value=float(request.metadata.get("task_value", 1.0)),
        )
        route = next(
            item
            for item in self.routes
            if item.model_profile_id == decision.state.model_profile_id
        )
        routed_request = replace(
            request,
            model_profile=route.model_name,
            metadata={
                **request.metadata,
                "routed_model_profile_id": str(route.model_profile_id),
                "routing_utility": decision.utility,
            },
        )
        response = await route.provider.generate(routed_request)
        response.raw_metadata = {
            **response.raw_metadata,
            "routed_model_profile_id": str(route.model_profile_id),
            "routing_utility": decision.utility,
        }
        return response
