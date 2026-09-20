import pytest

from packages.providers.base import ModelRequest
from packages.providers.fake import FakeProvider


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic() -> None:
    provider = FakeProvider(["first", "second"])

    first = await provider.generate(
        ModelRequest(
            model_profile="fake-model",
            messages=[{"role": "user", "content": "hello"}],
            task_type="research",
        )
    )
    second = await provider.generate(
        ModelRequest(
            model_profile="fake-model",
            messages=[{"role": "user", "content": "hello again"}],
            task_type="research",
        )
    )

    assert first.text == "first"
    assert second.text == "second"
    assert first.provider == "fake"
