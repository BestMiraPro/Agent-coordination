from __future__ import annotations

from collections import deque

from packages.providers.base import ModelRequest, ModelResponse


class FakeProvider:
    """Deterministic provider for unit and integration tests."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = deque(responses or [])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        text = self._responses.popleft() if self._responses else "{}"
        return ModelResponse(
            text=text,
            provider="fake",
            model=request.model_profile,
            latency_ms=0,
            estimated_cost=0.0,
        )
