"""Reference-artifact readiness checks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ReadinessProbe(Protocol):
    """Minimal port used to verify that analytical data can be queried."""

    def is_ready(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Framework-independent readiness result."""

    data_ready: bool
    checks: dict[str, bool]
    detail: str


class ReadinessService:
    """Verify both the artifact manifest and the configured analytical reader."""

    def __init__(self, artifact_directory: Path, probe: ReadinessProbe) -> None:
        self._artifact_directory = artifact_directory
        self._probe = probe

    def check(self) -> ReadinessResult:
        manifest_exists = (self._artifact_directory / "manifest.json").is_file()
        if not manifest_exists:
            return ReadinessResult(
                data_ready=False,
                checks={"artifact_reader": False, "reference_manifest": False},
                detail="Reference data manifest is not available; data endpoints are not ready.",
            )

        artifact_reader_ready = self._probe.is_ready()
        return ReadinessResult(
            data_ready=artifact_reader_ready,
            checks={"artifact_reader": artifact_reader_ready, "reference_manifest": True},
            detail=(
                "Reference artifacts are available and queryable."
                if artifact_reader_ready
                else "Reference manifest exists, but required artifacts cannot be queried."
            ),
        )
