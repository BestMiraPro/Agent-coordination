from __future__ import annotations

import json

import httpx
import pytest

from packages.providers.base import ModelRequest
from packages.providers.openai_compatible import (
    OpenAICompatibleProvider,
    ProviderRequestError,
    discover_openai_compatible_models,
)


def test_model_discovery_uses_bearer_auth_and_returns_ids() -> None:
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["project"] = request.headers["OpenAI-Project"]
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "deepseek-ai/DeepSeek-V3.1"},
                    {"id": "openai/gpt-oss-20b"},
                    {"id": "openai/gpt-oss-20b"},
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handle))
    models = discover_openai_compatible_models(
        base_url="https://api.inference.wandb.ai/v1",
        api_key="secret-test-key",
        project="team/project",
        client=client,
    )

    assert captured["authorization"] == "Bearer secret-test-key"
    assert captured["project"] == "team/project"
    assert models == [
        "deepseek-ai/DeepSeek-V3.1",
        "openai/gpt-oss-20b",
    ]
    client.close()


@pytest.mark.asyncio
async def test_openai_compatible_provider_sends_schema_and_project_header() -> None:
    captured: dict[str, object] = {}

    async def handle(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["project"] = request.headers["OpenAI-Project"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "openai/gpt-oss-20b",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": '{"ok":true}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "total_tokens": 16,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    provider = OpenAICompatibleProvider(
        base_url="https://api.inference.wandb.ai/v1",
        api_key="secret-test-key",
        provider_name="wandb",
        project="team/project",
        client=client,
    )
    response = await provider.generate(
        ModelRequest(
            model_profile="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": "Return JSON"}],
            task_type="research",
            response_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        )
    )

    body = captured["body"]
    assert isinstance(body, dict)
    assert captured["authorization"] == "Bearer secret-test-key"
    assert captured["project"] == "team/project"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert response.text == '{"ok":true}'
    assert response.input_tokens == 12
    assert response.output_tokens == 4

    await client.aclose()


@pytest.mark.asyncio
async def test_provider_retries_without_json_schema_when_model_rejects_it() -> None:
    bodies: list[dict[str, object]] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(400, text="response_format unsupported")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-fallback",
                "model": "some/model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": '{"ok":true}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="secret-test-key",
        provider_name="test-provider",
        client=client,
    )

    response = await provider.generate(
        ModelRequest(
            model_profile="some/model",
            messages=[{"role": "user", "content": "Return JSON"}],
            task_type="research",
            response_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        )
    )

    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert response.raw_metadata["structured_output_fallback"] is True
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_compatible_provider_wraps_http_errors() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="secret-test-key",
        provider_name="test-provider",
        client=client,
    )

    with pytest.raises(ProviderRequestError, match="HTTP 429"):
        await provider.generate(
            ModelRequest(
                model_profile="test-model",
                messages=[{"role": "user", "content": "hello"}],
                task_type="research",
            )
        )

    await client.aclose()
