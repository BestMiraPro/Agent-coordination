from uuid import uuid4

from packages.core.domain.models import ModelState
from packages.core.routing.adaptive import AdaptiveRouter


def test_router_prefers_high_value_low_pressure_capacity() -> None:
    fast_free = ModelState(
        model_profile_id=uuid4(),
        quality_by_task={"research": 0.78},
        marginal_cash_cost=0.0,
        credit_cost=0.1,
        latency_ms=300,
        scarcity=0.1,
        failure_rate=0.02,
        rate_limit_pressure=0.1,
        available_concurrency=4,
    )
    stronger_but_scarce = ModelState(
        model_profile_id=uuid4(),
        quality_by_task={"research": 0.9},
        marginal_cash_cost=0.0,
        credit_cost=0.0,
        latency_ms=2000,
        scarcity=0.95,
        failure_rate=0.05,
        rate_limit_pressure=0.9,
        available_concurrency=1,
    )

    decision = AdaptiveRouter().choose(
        "research",
        [stronger_but_scarce, fast_free],
    )

    assert decision.state.model_profile_id == fast_free.model_profile_id


def test_router_can_choose_expensive_stronger_model_for_high_quality_gap() -> None:
    cheap = ModelState(
        model_profile_id=uuid4(),
        quality_by_task={"critic": 0.2},
        marginal_cash_cost=0.0,
        latency_ms=300,
        scarcity=0.0,
        available_concurrency=4,
    )
    strong = ModelState(
        model_profile_id=uuid4(),
        quality_by_task={"critic": 0.95},
        marginal_cash_cost=0.05,
        latency_ms=500,
        scarcity=0.05,
        available_concurrency=2,
    )

    decision = AdaptiveRouter().choose("critic", [cheap, strong])

    assert decision.state.model_profile_id == strong.model_profile_id
