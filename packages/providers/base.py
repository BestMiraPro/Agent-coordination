from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ModelRequest:
    model_profile: str
    messages: list[dict[str, str]]
    task_type: str
    temperature: float = 0.2
    max_tokens: int | None = None
    response_schema: dict[str, Any] | None = None
    timeout_seconds: float = 120.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    retry_count: int = 0
    status: str = "ok"
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...
