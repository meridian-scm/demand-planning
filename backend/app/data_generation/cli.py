"""Command-line entry point for safe generation and validation."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from app.data_generation.artifacts import publish_artifacts, validate_published_artifacts
from app.data_generation.config import load_generator_config
from app.data_generation.generator import generate_artifacts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Meridian Parquet artifacts."
    )
    parser.add_argument("--config", type=Path, required=True, help="YAML generation profile")
    parser.add_argument("--output", type=Path, help="Override the configured output directory")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace an existing artifact version",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing published artifact set without generating data",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    project_root = Path(__file__).resolve().parents[3]
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = load_generator_config(config_path)
    if args.output is not None:
        config = config.model_copy(update={"output_directory": args.output})

    if args.validate_only:
        summary = validate_published_artifacts(config, project_root)
        result = {
            "status": "valid",
            "data_version": config.data_version,
            "output_directory": str(config.resolved_output_directory(project_root)),
            "row_counts": summary.row_counts,
        }
    else:
        bundle = generate_artifacts(config)
        manifest = publish_artifacts(bundle, config, project_root, overwrite=bool(args.overwrite))
        result = {
            "status": "generated",
            "data_version": manifest.data_version,
            "output_directory": str(config.resolved_output_directory(project_root)),
            "row_counts": manifest.row_counts,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
