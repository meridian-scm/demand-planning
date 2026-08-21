"""Repository-root wrapper for the backend synthetic-data CLI."""

import sys
from pathlib import Path


def _run() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "backend"))
    from app.data_generation.cli import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
