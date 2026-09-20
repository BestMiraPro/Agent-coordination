from uuid import uuid4

import pytest

from packages.core.domain.models import ModelState
from packages.providers.base import ModelRequest, ModelResponse
from packages.providers.routed import AdaptiveProvider, ProviderRoute


class RecordingProvider:
    def __init__(self) -> None:
        self.model: str | None = None

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.model = request.model_profile
        return ModelResponse(
            text="{}",
            provider="recording",
            model=request.model_profile,
        )


@pytest.mark.asyncio
async def test_adaptive_provider_records_route_metadata() -> None:
    profile_id = uuid4()
    underlying = RecordingProvider()
    state = ModelState(
        model_profile_id=profile_id,
        quality_by_task={"research": 0.8},
        available_concurrency=1,
    )
    provider = AdaptiveProvider(
        [
            ProviderRoute(
                model_profile_id=profile_id,
                model_name="test/model",
                provider=underlying,
                state=state,
            )
        ]
    )

    response = await provider.generate(
        ModelRequest(
            model_profile="logical/research",
            messages=[{"role": "user", "content": "test"}],
            task_type="research",
        )
    )

    assert underlying.model == "test/model"
    assert response.raw_metadata["routed_model_profile_id"] == str(profile_id)
    assert response.raw_metadata["routing_utility"] > 0
