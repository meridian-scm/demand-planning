"""Readiness checks available before analytical adapters are implemented."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Framework-independent readiness result."""

    data_ready: bool
    checks: dict[str, bool]
    detail: str


class ReadinessService:
    """Check only the reference-artifact evidence Step 1 can verify honestly."""

    def __init__(self, artifact_directory: Path) -> None:
        self._artifact_directory = artifact_directory

    def check(self) -> ReadinessResult:
        manifest_exists = (self._artifact_directory / "manifest.json").is_file()
        if not manifest_exists:
            return ReadinessResult(
                data_ready=False,
                checks={"artifact_reader": False, "reference_manifest": False},
                detail="Reference data manifest is not available; data endpoints are not ready.",
            )

        return ReadinessResult(
            data_ready=False,
            checks={"artifact_reader": False, "reference_manifest": True},
            detail="Reference manifest exists, but the artifact reader is not implemented yet.",
        )
