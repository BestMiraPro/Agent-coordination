from __future__ import annotations

from dataclasses import dataclass
from math import log1p

from packages.core.domain.models import ModelState


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    state: ModelState
    utility: float
    task_type: str


class AdaptiveRouter:
    """Choose the highest expected-value model under cost/latency/scarcity pressure."""

    def __init__(
        self,
        *,
        cash_weight: float = 1.0,
        credit_weight: float = 0.35,
        latency_weight: float = 0.08,
        scarcity_weight: float = 0.8,
        rate_limit_weight: float = 0.8,
    ) -> None:
        self.cash_weight = cash_weight
        self.credit_weight = credit_weight
        self.latency_weight = latency_weight
        self.scarcity_weight = scarcity_weight
        self.rate_limit_weight = rate_limit_weight

    def choose(
        self,
        task_type: str,
        states: list[ModelState],
        *,
        task_value: float = 1.0,
    ) -> RoutingDecision:
        candidates = [
            state
            for state in states
            if state.enabled and state.available_concurrency > 0
        ]
        if not candidates:
            raise RuntimeError("No model capacity is currently available")

        scored = [
            RoutingDecision(
                state=state,
                utility=self.utility(
                    state,
                    task_type=task_type,
                    task_value=task_value,
                ),
                task_type=task_type,
            )
            for state in candidates
        ]
        scored.sort(
            key=lambda item: (
                -item.utility,
                item.state.failure_rate,
                item.state.latency_ms,
                str(item.state.model_profile_id),
            )
        )
        return scored[0]

    def utility(
        self,
        state: ModelState,
        *,
        task_type: str,
        task_value: float = 1.0,
    ) -> float:
        quality = state.quality_by_task.get(
            task_type,
            state.quality_by_task.get("default", 0.5),
        )
        reliability = max(0.01, 1.0 - state.failure_rate)
        concurrency_bonus = 1.0 + 0.08 * log1p(state.available_concurrency)

        pressure = (
            0.05
            + self.cash_weight * max(0.0, state.marginal_cash_cost)
            + self.credit_weight * max(0.0, state.credit_cost)
            + self.latency_weight * max(0.0, state.latency_ms) / 1000.0
            + self.scarcity_weight * max(0.0, state.scarcity)
            + self.rate_limit_weight * max(0.0, state.rate_limit_pressure)
        )
        return (
            max(0.0, quality)
            * reliability
            * max(0.0, task_value)
            * concurrency_bonus
            / pressure
        )
