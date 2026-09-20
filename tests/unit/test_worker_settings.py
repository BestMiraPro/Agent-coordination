from pydantic import SecretStr

from services.worker.worker.settings import WorkerSettings


def test_wandb_api_key_is_accepted_as_native_fallback() -> None:
    settings = WorkerSettings(
        inference_provider="wandb",
        inference_api_key=None,
        wandb_api_key=SecretStr("native-key"),
    )

    resolved = settings.resolved_api_key()
    assert resolved is not None
    assert resolved.get_secret_value() == "native-key"


def test_generic_inference_key_takes_precedence() -> None:
    settings = WorkerSettings(
        inference_provider="wandb",
        inference_api_key=SecretStr("generic-key"),
        wandb_api_key=SecretStr("native-key"),
    )

    resolved = settings.resolved_api_key()
    assert resolved is not None
    assert resolved.get_secret_value() == "generic-key"
