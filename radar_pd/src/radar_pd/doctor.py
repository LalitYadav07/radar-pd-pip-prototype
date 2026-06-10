from __future__ import annotations

import json
import platform
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import installed_packs


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _check_python() -> Check:
    version = platform.python_version()
    if sys.version_info[:2] == (3, 12):
        return Check("python", "PASS", version)
    return Check("python", "FAIL", f"{version}; expected Python 3.12.x")


def _check_runtime() -> tuple[Check, str | None]:
    try:
        import radar_pd_gsasii_runtime as runtime

        root = runtime.activate()
    except Exception as exc:  # pragma: no cover - diagnostic path
        return Check("gsasii-runtime", "FAIL", repr(exc)), None
    return Check("gsasii-runtime", "PASS", root), root


def _check_gsasii_import() -> Check:
    try:
        import GSASII.GSASIIscriptable as G2sc
    except Exception as exc:  # pragma: no cover - diagnostic path
        return Check("gsasii-import", "FAIL", repr(exc))
    return Check("gsasii-import", "PASS", str(Path(G2sc.__file__).resolve()))


def _check_gsasii_project() -> Check:
    try:
        import GSASII.GSASIIscriptable as G2sc

        with tempfile.TemporaryDirectory(prefix="radar_pd_gsasii_") as tmp:
            gpx = Path(tmp) / "doctor.gpx"
            project = G2sc.G2Project(newgpx=str(gpx))
            project.save()
            if not gpx.exists():
                return Check("gsasii-project", "FAIL", f"Project was not written: {gpx}")
    except Exception as exc:  # pragma: no cover - diagnostic path
        return Check("gsasii-project", "FAIL", repr(exc))
    return Check("gsasii-project", "PASS", "created and saved a minimal .gpx")


def _check_data(require_data: bool) -> Check:
    packs = installed_packs()
    if packs:
        names = ", ".join(path.name for path in packs)
        return Check("data-packs", "PASS", names)
    if require_data:
        return Check("data-packs", "FAIL", "no database packs installed")
    return Check("data-packs", "WARN", "no database packs installed")


def run_doctor(
    *,
    json_output: bool = False,
    require_data: bool = False,
    smoke_gsas_project: bool = False,
) -> int:
    checks: list[Check] = []
    checks.append(_check_python())
    runtime_check, _root = _check_runtime()
    checks.append(runtime_check)
    if runtime_check.status == "PASS":
        checks.append(_check_gsasii_import())
        if smoke_gsas_project:
            checks.append(_check_gsasii_project())
    checks.append(_check_data(require_data=require_data))

    if json_output:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        width = max(len(check.name) for check in checks)
        for check in checks:
            print(f"{check.name:<{width}}  {check.status:<4}  {check.detail}")

    return 1 if any(check.status == "FAIL" for check in checks) else 0

