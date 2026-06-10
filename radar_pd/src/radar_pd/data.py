from __future__ import annotations

import os
import shutil
from pathlib import Path

from platformdirs import user_cache_dir


APP_NAME = "radar-pd"


def cache_root() -> Path:
    override = os.environ.get("RADAR_PD_CACHE_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(user_cache_dir(APP_NAME)).resolve()


def data_root() -> Path:
    override = os.environ.get("RADAR_PD_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return cache_root() / "data"


def pack_root() -> Path:
    return data_root() / "packs"


def installed_packs() -> list[Path]:
    root = pack_root()
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def install_data(
    *,
    name: str,
    source: str | None = None,
    hf_repo: str | None = None,
    hf_revision: str | None = None,
    force: bool = False,
) -> Path:
    if bool(source) == bool(hf_repo):
        raise SystemExit("Provide exactly one of --source or --hf-repo.")

    target = pack_root() / name
    if target.exists():
        if not force:
            raise SystemExit(f"Data pack already exists: {target}. Use --force to replace it.")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    if source:
        src = Path(source).expanduser().resolve()
        if not src.is_dir():
            raise SystemExit(f"--source is not a directory: {src}")
        shutil.copytree(src, target)
    else:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=hf_repo,
            repo_type="dataset",
            revision=hf_revision,
            local_dir=str(target),
            local_dir_use_symlinks=False,
        )

    print(f"Installed data pack '{name}' at {target}")
    return target


def print_paths() -> None:
    print(f"cache_root: {cache_root()}")
    print(f"data_root:  {data_root()}")
    print(f"pack_root:  {pack_root()}")
    packs = installed_packs()
    if packs:
        print("packs:")
        for path in packs:
            print(f"  - {path.name}: {path}")
    else:
        print("packs:      none")

