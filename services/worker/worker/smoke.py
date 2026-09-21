from __future__ import annotations

import asyncio
import json

from packages.providers.base import ModelRequest
from services.worker.worker.main import build_provider
from services.worker.worker.settings import WorkerSettings


async def main() -> None:
    settings = WorkerSettings()
    if settings.inference_provider == "fake":
        raise SystemExit(
            "Refusing fake smoke test. Set INFERENCE_PROVIDER=wandb first."
        )

    provider, provider_name, primary_model, model_names, _ = build_provider(settings)
    print(
        f"provider={provider_name} primary_model={primary_model} "
        f"discovered_models={len(model_names)}"
    )
    response = await provider.generate(
        ModelRequest(
            model_profile=primary_model,
            task_type="real_inference_smoke",
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON matching the schema.",
                },
                {
                    "role": "user",
                    "content": "Return {\"real_inference\": true, \"answer\": \"W&B reached\"}.",
                },
            ],
            response_schema={
                "type": "object",
                "properties": {
                    "real_inference": {"type": "boolean"},
                    "answer": {"type": "string"},
                },
                "required": ["real_inference", "answer"],
                "additionalProperties": False,
            },
            temperature=0.0,
            max_tokens=100,
        )
    )
    payload = json.loads(response.text)
    if payload.get("real_inference") is not True:
        raise SystemExit("Real inference smoke response failed validation")
    print(
        f"SUCCESS provider={response.provider} model={response.model} "
        f"latency_ms={response.latency_ms} input_tokens={response.input_tokens} "
        f"output_tokens={response.output_tokens}"
    )
    if hasattr(provider, "aclose"):
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
