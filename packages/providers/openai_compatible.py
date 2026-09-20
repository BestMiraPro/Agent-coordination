from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from packages.providers.base import ModelRequest, ModelResponse


class ProviderRequestError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat-completions endpoints.

    The adapter is intentionally vendor-neutral. W&B Inference is the first
    production target, but any compatible endpoint can be configured.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        provider_name: str,
        project: str | None = None,
        supports_json_schema: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider_name = provider_name
        self.project = project
        self.supports_json_schema = supports_json_schema
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def generate(self, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": request.model_profile,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_schema is not None and self.supports_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{request.task_type}_response",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.project:
            headers["OpenAI-Project"] = self.project

        started = perf_counter()
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=request.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                f"{self.provider_name} request failed: {type(exc).__name__}"
            ) from exc

        latency_ms = round((perf_counter() - started) * 1000)

        if response.is_error:
            detail = response.text[:500]
            raise ProviderRequestError(
                f"{self.provider_name} returned HTTP {response.status_code}: {detail}"
            )

        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError(
                f"{self.provider_name} returned an invalid chat-completions response"
            ) from exc

        if not isinstance(content, str):
            raise ProviderRequestError(
                f"{self.provider_name} returned non-text message content"
            )

        usage = data.get("usage") or {}
        model = data.get("model") or request.model_profile

        return ModelResponse(
            text=content,
            provider=self.provider_name,
            model=str(model),
            latency_ms=latency_ms,
            input_tokens=_optional_int(usage.get("prompt_tokens")),
            output_tokens=_optional_int(usage.get("completion_tokens")),
            raw_metadata={
                "id": data.get("id"),
                "finish_reason": choice.get("finish_reason"),
                "usage": usage,
                "response_model": model,
            },
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None
