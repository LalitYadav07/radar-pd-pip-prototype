from __future__ import annotations

import argparse
import sys

from .commands import run_pipeline, run_ui
from .data import install_data, print_paths
from .doctor import run_doctor


def _doctor(args: argparse.Namespace) -> int:
    return run_doctor(
        json_output=args.json,
        require_data=args.require_data,
        smoke_gsas_project=args.smoke_gsas_project,
    )


def _install_data(args: argparse.Namespace) -> int:
    install_data(
        name=args.name,
        source=args.source,
        hf_repo=args.hf_repo,
        hf_revision=args.hf_revision,
        force=args.force,
    )
    return 0


def _paths(_args: argparse.Namespace) -> int:
    print_paths()
    return 0


def _ui(args: argparse.Namespace) -> int:
    return run_ui(
        source_root=args.source_root,
        port=args.port,
        address=args.address,
        check_only=args.check_only,
        streamlit_args=args.streamlit_args,
    )


def _run(args: argparse.Namespace) -> int:
    return run_pipeline(
        source_root=args.source_root,
        config=args.config,
        dataset=args.dataset,
        dry_run=args.dry_run,
        check_only=args.check_only,
        skip_preflight=args.skip_preflight,
        passthrough_args=args.pipeline_args,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="radar-pd")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check the RADAR-PD runtime.")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    doctor.add_argument(
        "--require-data",
        action="store_true",
        help="Fail when no database packs are installed.",
    )
    doctor.add_argument(
        "--smoke-gsas-project",
        action="store_true",
        help="Create a tiny GSAS-II project as a runtime smoke test.",
    )
    doctor.set_defaults(func=_doctor)

    install = subparsers.add_parser("install-data", help="Install a database pack.")
    install.add_argument("--name", default="standard", help="Local pack name.")
    install.add_argument("--source", help="Copy a local directory into the data cache.")
    install.add_argument("--hf-repo", help="Download a dataset repository from Hugging Face Hub.")
    install.add_argument("--hf-revision", help="Optional Hugging Face revision.")
    install.add_argument("--force", action="store_true", help="Replace an existing pack.")
    install.set_defaults(func=_install_data)

    paths = subparsers.add_parser("paths", help="Show cache/runtime paths.")
    paths.set_defaults(func=_paths)

    ui = subparsers.add_parser("ui", help="Launch the RADAR-PD Streamlit UI.")
    ui.add_argument("--source-root", help="Existing RADAR-PD source checkout.")
    ui.add_argument("--port", type=int, default=8501)
    ui.add_argument("--address", default="127.0.0.1")
    ui.add_argument("--check-only", action="store_true", help="Validate and print command only.")
    ui.add_argument(
        "streamlit_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to Streamlit.",
    )
    ui.set_defaults(func=_ui)

    run = subparsers.add_parser("run", help="Run the RADAR-PD CLI pipeline.")
    run.add_argument("--source-root", help="Existing RADAR-PD source checkout.")
    run.add_argument("--config", required=True, help="Pipeline config YAML.")
    run.add_argument("--dataset", help="Dataset name to run.")
    run.add_argument("--dry-run", action="store_true", help="Validate config and exit.")
    run.add_argument("--check-only", action="store_true", help="Validate and print command only.")
    run.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip optional dependency checks and call the pipeline directly.",
    )
    run.add_argument(
        "pipeline_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to the pipeline script.",
    )
    run.set_defaults(func=_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        args = parser.parse_args(["doctor"])
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
