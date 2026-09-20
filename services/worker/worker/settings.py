from __future__ import annotations

from socket import gethostname
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    worker_id: str = Field(default_factory=lambda: f"worker-{gethostname()}")
    worker_poll_interval_seconds: float = 0.5

    inference_provider: Literal["fake", "wandb", "openai_compatible"] = "fake"
    inference_model: str = "openai/gpt-oss-20b"
    inference_base_url: str = "https://api.inference.wandb.ai/v1"
    inference_api_key: SecretStr | None = None
    inference_project: str | None = None
    inference_structured_outputs: bool = True
