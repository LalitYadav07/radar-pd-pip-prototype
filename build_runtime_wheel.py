from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


RUNTIME_VERSION = "0.0.1"

EXCLUDED_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    "build",
    "docs",
    "pixi",
    "tests",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".pyd",
    ".dll",
    ".exe",
}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in EXCLUDED_DIRS:
            ignored.add(name)
        elif any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
            ignored.add(name)
    return ignored


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _download_binary_bundle(url: str, gsasii_package_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "gsasii-binaries.tgz"
        urllib.request.urlretrieve(url, archive)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(gsasii_package_dir, filter="data")


def build_runtime_wheel(
    gsasii_root: Path,
    work_dir: Path,
    out_dir: Path,
    binary_bundle_url: str | None,
    numpy_requirement: str,
) -> Path:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Build this prototype with Python 3.12.")

    gsasii_root = gsasii_root.resolve()
    if not (gsasii_root / "GSASII").is_dir():
        raise SystemExit(f"GSAS-II root does not contain GSASII/: {gsasii_root}")

    stage = work_dir.resolve() / "radar-pd-gsasii-runtime"
    if stage.exists():
        shutil.rmtree(stage)
    out_dir.mkdir(parents=True, exist_ok=True)

    pkg = stage / "src" / "radar_pd_gsasii_runtime"
    runtime_tree = pkg / "gsasii"
    gsasii_package_dir = runtime_tree / "GSASII"
    pkg.mkdir(parents=True, exist_ok=True)
    shutil.copytree(gsasii_root, runtime_tree, ignore=_ignore)

    if binary_bundle_url:
        _download_binary_bundle(binary_bundle_url, gsasii_package_dir)

    _write_text(
        stage / "pyproject.toml",
        f"""[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "radar-pd-gsasii-runtime"
version = "{RUNTIME_VERSION}"
description = "Pinned GSAS-II runtime snapshot for RADAR-PD"
requires-python = ">=3.12,<3.13"
dependencies = [
  "{numpy_requirement}",
  "scipy>=1.15",
  "matplotlib>=3.10",
  "pillow>=11",
  "h5py>=3.12",
  "imageio>=2.36",
  "PyCifRW>=4.4",
  "requests>=2.32",
  "xmltodict>=0.14",
  "setuptools",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
radar_pd_gsasii_runtime = ["gsasii/**/*"]
""",
    )
    _write_text(
        stage / "MANIFEST.in",
        "recursive-include src/radar_pd_gsasii_runtime/gsasii *\n",
    )
    _write_text(
        stage / "setup.py",
        """from setuptools import setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(distclass=BinaryDistribution)
""",
    )
    _write_text(
        pkg / "__init__.py",
        '''from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

__all__ = ["activate", "gsasii_path", "gsasii_package_path"]


def gsasii_path() -> str:
    """Return the GSAS-II root used by RADAR-PD."""

    override = os.environ.get("RADAR_PD_GSASII_ROOT")
    if override:
        return str(Path(override).expanduser().resolve())
    return str(resources.files(__name__).joinpath("gsasii"))


def gsasii_package_path() -> str:
    return str(Path(gsasii_path()) / "GSASII")


def activate(prepend: bool = True) -> str:
    """Add the bundled GSAS-II root to `sys.path` and return it."""

    root = Path(gsasii_path())
    if not (root / "GSASII").is_dir():
        raise RuntimeError(f"Invalid GSAS-II runtime root: {root}")
    root_str = str(root)
    if root_str not in sys.path:
        if prepend:
            sys.path.insert(0, root_str)
        else:
            sys.path.append(root_str)
    os.environ.setdefault("RADAR_PD_GSASII_ROOT", root_str)
    return root_str
''',
    )

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(stage), "-w", str(out_dir), "--no-deps"],
        check=True,
    )
    wheels = sorted(out_dir.glob("radar_pd_gsasii_runtime-*.whl"))
    if not wheels:
        raise SystemExit("Runtime wheel build completed but no wheel was found.")
    return wheels[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a RADAR-PD GSAS-II runtime wheel.")
    parser.add_argument("--gsasii-root", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=Path(".tmp") / "runtime-wheel-build")
    parser.add_argument("--out-dir", type=Path, default=Path("wheelhouse"))
    parser.add_argument("--binary-bundle-url", default=None)
    parser.add_argument("--numpy-requirement", default="numpy<2")
    args = parser.parse_args()
    wheel = build_runtime_wheel(
        args.gsasii_root,
        args.work_dir,
        args.out_dir,
        args.binary_bundle_url,
        args.numpy_requirement,
    )
    print(f"Built {wheel}")


if __name__ == "__main__":
    main()
