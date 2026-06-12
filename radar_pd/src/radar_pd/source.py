from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ENV = "RADAR_PD_SOURCE_ROOT"


def _looks_like_source_root(path: Path) -> bool:
    return (
        (path / "app.py").is_file()
        and (path / "scripts" / "gsas_complete_pipeline_nomain.py").is_file()
    )


def find_source_root(source_root: str | None = None) -> Path:
    """Find an existing RADAR-PD source tree without modifying it."""

    candidates: list[Path] = []
    if source_root:
        candidates.append(Path(source_root))
    env_root = os.environ.get(SOURCE_ENV)
    if env_root:
        candidates.append(Path(env_root))

    cwd = Path.cwd()
    candidates.extend([cwd, *cwd.parents])

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if _looks_like_source_root(resolved):
            return resolved

    raise SystemExit(
        "Could not find a RADAR-PD source root. Run from the repository root or "
        f"pass --source-root /path/to/repo or set {SOURCE_ENV}."
    )


def activate_runtime_and_source(source_root: Path) -> dict[str, str]:
    """Activate bundled GSAS-II and return env vars for child processes."""

    import radar_pd_gsasii_runtime as runtime

    gsas_root = Path(runtime.activate()).resolve()
    scripts_root = source_root / "scripts"
    for path in (scripts_root, source_root, gsas_root):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONSAFEPATH"] = "1"
    env[SOURCE_ENV] = str(source_root)
    env["RADAR_PD_GSASII_ROOT"] = str(gsas_root)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(gsas_root), str(scripts_root), str(source_root), existing_pythonpath])
    )
    return env


def require_import(module_name: str, install_hint: str) -> None:
    try:
        __import__(module_name)
    except ImportError as exc:
        raise SystemExit(
            f"Missing optional dependency '{module_name}'. Install {install_hint} "
            f"before running this command. Original error: {exc}"
        ) from exc


def require_imports(module_names: list[str], install_hint: str) -> None:
    missing: list[str] = []
    for module_name in module_names:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        formatted = ", ".join(missing)
        raise SystemExit(
            f"Missing optional dependencies: {formatted}. Install {install_hint} "
            "before running this command."
        )
