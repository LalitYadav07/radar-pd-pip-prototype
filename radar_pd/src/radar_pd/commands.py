from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .source import activate_runtime_and_source, find_source_root, require_import, require_imports


def run_ui(
    *,
    source_root: str | None,
    port: int,
    address: str,
    check_only: bool,
    streamlit_args: list[str],
) -> int:
    root = find_source_root(source_root)
    env = activate_runtime_and_source(root)
    app_path = root / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        address,
        "--browser.gatherUsageStats=false",
        *streamlit_args,
    ]

    if check_only:
        print(f"source_root: {root}")
        print(f"gsasii_root:  {env['RADAR_PD_GSASII_ROOT']}")
        print("command:     " + " ".join(cmd))
        return 0

    require_import("streamlit", "with `pip install 'radar-pd[app]'`")
    return subprocess.call(cmd, cwd=str(root), env=env)


def run_pipeline(
    *,
    source_root: str | None,
    config: str,
    dataset: str | None,
    dry_run: bool,
    check_only: bool,
    skip_preflight: bool,
    passthrough_args: list[str],
) -> int:
    root = find_source_root(source_root)
    env = activate_runtime_and_source(root)
    script = root / "scripts" / "gsas_complete_pipeline_nomain.py"
    config_path = Path(config).expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    if not config_path.is_file():
        raise SystemExit(f"Config file not found: {config_path}")

    cmd = [sys.executable, str(script), "--config", str(config_path)]
    if dataset:
        cmd.extend(["--dataset", dataset])
    if dry_run:
        cmd.append("--dry-run")
        env.setdefault("SKIP_COMPONENT_CHECK", "1")
    cmd.extend(passthrough_args)

    if check_only:
        print(f"source_root: {root}")
        print(f"gsasii_root:  {env['RADAR_PD_GSASII_ROOT']}")
        print(f"config:      {config_path}")
        print("command:     " + " ".join(cmd))
        return 0

    if not skip_preflight:
        require_imports(
            ["pandas", "sklearn", "pymatgen", "torch"],
            "with `pip install 'radar-pd[app]'`",
        )

    return subprocess.call(cmd, cwd=str(root), env=env)
