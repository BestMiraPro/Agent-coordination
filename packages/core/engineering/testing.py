from __future__ import annotations

import json
from pathlib import PurePosixPath

from packages.core.domain.models import EngineeringCheck


class EngineeringTestRunner:
    """Deterministic static checks for generated engineering artifacts."""

    def run(
        self,
        *,
        engineering_run_id,
        repair_cycle: int,
        implementation_payloads: list[dict[str, object]],
    ) -> list[EngineeringCheck]:
        files: list[dict[str, str]] = []
        for payload in implementation_payloads:
            for item in payload.get("files", []):
                if isinstance(item, dict):
                    path = item.get("path")
                    content = item.get("content")
                    if isinstance(path, str) and isinstance(content, str):
                        files.append({"path": path, "content": content})

        checks: list[EngineeringCheck] = []
        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="files_present",
                passed=bool(files),
                detail=(
                    f"{len(files)} generated files available."
                    if files
                    else "No generated files were provided."
                ),
                repair_cycle=repair_cycle,
            )
        )

        unsafe = [item["path"] for item in files if not self._safe_path(item["path"])]
        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="safe_paths",
                passed=not unsafe,
                detail=(
                    "All generated paths are relative and sandbox-safe."
                    if not unsafe
                    else f"Unsafe paths: {unsafe}"
                ),
                repair_cycle=repair_cycle,
            )
        )

        paths = [item["path"] for item in files]
        duplicates = sorted({path for path in paths if paths.count(path) > 1})
        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="unique_paths",
                passed=not duplicates,
                detail=(
                    "Generated file paths are unique."
                    if not duplicates
                    else f"Duplicate paths: {duplicates}"
                ),
                repair_cycle=repair_cycle,
            )
        )

        syntax_errors: list[str] = []
        json_errors: list[str] = []
        for item in files:
            path = item["path"]
            content = item["content"]
            if path.endswith(".py"):
                try:
                    compile(content, f"<generated:{path}>", "exec")
                except SyntaxError as exc:
                    syntax_errors.append(
                        f"{path}: {exc.msg} at line {exc.lineno}"
                    )
            if path.endswith(".json"):
                try:
                    json.loads(content)
                except json.JSONDecodeError as exc:
                    json_errors.append(
                        f"{path}: {exc.msg} at line {exc.lineno}"
                    )

        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="python_compile",
                passed=not syntax_errors,
                detail=(
                    "All generated Python files compile."
                    if not syntax_errors
                    else "; ".join(syntax_errors)
                ),
                repair_cycle=repair_cycle,
            )
        )
        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="json_parse",
                passed=not json_errors,
                detail=(
                    "All generated JSON files parse."
                    if not json_errors
                    else "; ".join(json_errors)
                ),
                repair_cycle=repair_cycle,
            )
        )

        test_files = [
            item["path"]
            for item in files
            if "test" in PurePosixPath(item["path"]).name.lower()
            or "tests" in PurePosixPath(item["path"]).parts
        ]
        checks.append(
            EngineeringCheck(
                engineering_run_id=engineering_run_id,
                name="test_artifact_present",
                passed=bool(test_files),
                detail=(
                    f"Test artifacts present: {test_files}"
                    if test_files
                    else "No test artifact was generated."
                ),
                repair_cycle=repair_cycle,
            )
        )
        return checks

    @staticmethod
    def all_passed(checks: list[EngineeringCheck]) -> bool:
        return bool(checks) and all(check.passed for check in checks)

    @staticmethod
    def _safe_path(path: str) -> bool:
        candidate = PurePosixPath(path)
        return (
            bool(path.strip())
            and not candidate.is_absolute()
            and ".." not in candidate.parts
            and path not in {".", "./"}
        )
