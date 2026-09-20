from __future__ import annotations

import json

from packages.core.domain.models import EngineeringRun
from packages.core.structured_outputs import (
    EngineeringImplementationOutput,
    EngineeringPlanOutput,
    EngineeringReviewOutput,
)
from packages.providers.base import ModelRequest


def build_engineering_plan_request(
    run: EngineeringRun,
    model_profile: str,
) -> ModelRequest:
    schema = EngineeringPlanOutput.model_json_schema()
    return ModelRequest(
        model_profile=model_profile,
        task_type="engineering_plan",
        temperature=0.2,
        max_tokens=4000,
        response_schema=schema,
        metadata={"engineering_run_id": str(run.id), "task_value": 1.2},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the engineering planner. Produce a concrete implementation "
                    "plan with independently testable tasks and explicit risks. Return only "
                    "JSON matching the schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": run.title,
                        "objective": run.objective,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )


def build_engineering_implementation_request(
    run: EngineeringRun,
    plan: dict[str, object],
    role: str,
    model_profile: str,
) -> ModelRequest:
    schema = EngineeringImplementationOutput.model_json_schema()
    return ModelRequest(
        model_profile=model_profile,
        task_type="engineering_implement",
        temperature=0.25,
        max_tokens=7000,
        response_schema=schema,
        metadata={
            "engineering_run_id": str(run.id),
            "engineering_role": role,
            "task_value": 1.0,
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a specialized implementation agent. Produce concrete file "
                    "artifacts for your assigned role. Paths must be relative. Return only "
                    "JSON matching the schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": run.title,
                        "objective": run.objective,
                        "plan": plan,
                        "role": role,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )


def build_engineering_review_request(
    run: EngineeringRun,
    artifacts: list[dict[str, object]],
    checks: list[dict[str, object]],
    model_profile: str,
) -> ModelRequest:
    schema = EngineeringReviewOutput.model_json_schema()
    tests_passed = bool(checks) and all(bool(item.get("passed")) for item in checks)
    return ModelRequest(
        model_profile=model_profile,
        task_type="engineering_review",
        temperature=0.1,
        max_tokens=4000,
        response_schema=schema,
        metadata={
            "engineering_run_id": str(run.id),
            "tests_passed": tests_passed,
            "task_value": 1.3,
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the final system reviewer. Check architecture, correctness, "
                    "tests, and systemic risks. Never approve while deterministic checks "
                    "are failing. Return only JSON matching the schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "objective": run.objective,
                        "artifacts": artifacts,
                        "deterministic_checks": checks,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )


def build_engineering_repair_request(
    run: EngineeringRun,
    artifacts: list[dict[str, object]],
    checks: list[dict[str, object]],
    review: dict[str, object],
    model_profile: str,
) -> ModelRequest:
    schema = EngineeringImplementationOutput.model_json_schema()
    return ModelRequest(
        model_profile=model_profile,
        task_type="engineering_repair",
        temperature=0.2,
        max_tokens=7000,
        response_schema=schema,
        metadata={
            "engineering_run_id": str(run.id),
            "repair_cycle": run.repair_count + 1,
            "task_value": 1.2,
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the repair engineer. Return a corrected complete file set that "
                    "addresses deterministic failures and reviewer issues. Return only JSON "
                    "matching the schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "objective": run.objective,
                        "current_artifacts": artifacts,
                        "checks": checks,
                        "review": review,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
