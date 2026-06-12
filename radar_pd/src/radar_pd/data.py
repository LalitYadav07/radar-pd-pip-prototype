from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from platformdirs import user_cache_dir


APP_NAME = "radar-pd"
CATALOG_ARCHIVES = {
    "neutron": {
        "display_name": "Neutron database",
        "google_drive_id": "1BxPXjdbn7oYTXKfDeLct5-2PMkhcLVSH",
        "target_dir": "database_neutron",
        "profile_kind": "directory",
    },
    "xray": {
        "display_name": "X-ray database",
        "google_drive_id": "12H19jI3mGcYBpJrQRtY-5_WaMjFyIMah",
        "target_dir": "database_xray",
        "profile_kind": "file",
    },
}
CATALOG_CHOICES = ("all", *CATALOG_ARCHIVES.keys())
_DB_WRAPPER_DIRS = {"database_aug", "database_xray", "database_neutron"}
_REQUIRED_COMMON = ("catalog_deduplicated.csv", "mp_experimental_stable.csv")


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


def _repair_database_layout(target_db_dir: Path) -> bool:
    """Normalize archive layouts with wrapper folders or Windows path separators."""

    target_db_dir = Path(target_db_dir)
    if not target_db_dir.exists():
        return False

    changed = False
    files_to_move = [path for path in target_db_dir.rglob("*") if path.is_file()]
    for src in files_to_move:
        rel = src.relative_to(target_db_dir).as_posix().replace("\\", "/")
        parts = [part for part in rel.split("/") if part not in ("", ".")]
        if parts and parts[0] in _DB_WRAPPER_DIRS:
            parts = parts[1:]
        if not parts:
            continue

        dest = target_db_dir.joinpath(*parts)
        if dest == src:
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(src), str(dest))
        changed = True

    for root, dirs, _files in os.walk(target_db_dir, topdown=False):
        for dirname in dirs:
            path = Path(root) / dirname
            try:
                if path.exists() and not any(path.iterdir()):
                    path.rmdir()
                    changed = True
            except OSError:
                pass

    return changed


def _catalog_is_valid(target_db_dir: Path, *, profile_kind: str) -> bool:
    target_db_dir = Path(target_db_dir)
    if not target_db_dir.exists():
        return False
    _repair_database_layout(target_db_dir)
    for filename in _REQUIRED_COMMON:
        if not (target_db_dir / filename).exists():
            return False
    if not (target_db_dir / "highsymm_metadata.json").exists():
        return False
    if profile_kind == "file":
        return (target_db_dir / "profiles64.npz").exists()
    profiles_dir = target_db_dir / "profiles64"
    return profiles_dir.is_dir() and any(profiles_dir.iterdir())


def _resolve_extracted_database_root(extract_dir: Path, target_dir_name: str) -> Path:
    for candidate_name in (target_dir_name, "database_aug", "database_xray", "database_neutron"):
        candidate = extract_dir / candidate_name
        if candidate.exists():
            return candidate
    return extract_dir


def _extract_catalog_archive(archive_path: Path, target_db_dir: Path, *, target_dir_name: str) -> None:
    if not zipfile.is_zipfile(archive_path):
        raise SystemExit(f"Downloaded catalog is not a valid ZIP archive: {archive_path}")

    with tempfile.TemporaryDirectory(prefix="radar-pd-catalog-") as tmp:
        extract_dir = Path(tmp) / "extract"
        extract_dir.mkdir(parents=True)
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                normalized = member.filename.replace("\\", "/")
                parts = [part for part in normalized.split("/") if part not in ("", ".")]
                if normalized.startswith("/") or ".." in parts:
                    raise SystemExit(f"Refusing unsafe catalog archive member: {member.filename}")
                archive.extract(member, extract_dir)

        _repair_database_layout(extract_dir)
        extracted_root = _resolve_extracted_database_root(extract_dir, target_dir_name)
        target_db_dir.mkdir(parents=True, exist_ok=True)
        for item in extracted_root.iterdir():
            dest = target_db_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        _repair_database_layout(target_db_dir)


def _download_google_drive_file(file_id: str, output_path: Path) -> None:
    try:
        import gdown
    except ImportError as exc:
        raise SystemExit(
            "Google Drive catalog download requires gdown. Reinstall with "
            "`pip install 'radar-pd[app]'` or install `gdown`."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = gdown.download(id=file_id, output=str(output_path), quiet=False)
    if not result or not output_path.exists():
        raise SystemExit(f"Catalog download failed for Google Drive file id: {file_id}")


def install_builtin_catalogs(
    *,
    source_root: str | Path,
    catalog: str = "all",
    force: bool = False,
) -> list[Path]:
    if catalog not in CATALOG_CHOICES:
        choices = ", ".join(CATALOG_CHOICES)
        raise SystemExit(f"Unknown catalog '{catalog}'. Choose one of: {choices}")

    source = Path(source_root).expanduser().resolve()
    if not (source / "app.py").is_file():
        raise SystemExit(f"--source-root does not look like a RADAR-PD checkout: {source}")

    keys = list(CATALOG_ARCHIVES) if catalog == "all" else [catalog]
    installed: list[Path] = []
    data_dir = source / "data"
    archive_cache = cache_root() / "catalog_archives"

    for key in keys:
        spec = CATALOG_ARCHIVES[key]
        target = data_dir / str(spec["target_dir"])
        if _catalog_is_valid(target, profile_kind=str(spec["profile_kind"])) and not force:
            print(f"{spec['display_name']} already installed at {target}")
            installed.append(target)
            continue

        if target.exists():
            shutil.rmtree(target)

        archive_path = archive_cache / f"{spec['target_dir']}.zip"
        print(f"Downloading {spec['display_name']}...")
        _download_google_drive_file(str(spec["google_drive_id"]), archive_path)
        print(f"Installing {spec['display_name']} into {target}")
        _extract_catalog_archive(
            archive_path,
            target,
            target_dir_name=str(spec["target_dir"]),
        )

        if not _catalog_is_valid(target, profile_kind=str(spec["profile_kind"])):
            raise SystemExit(f"{spec['display_name']} did not pass layout validation after install: {target}")
        installed.append(target)
        print(f"Installed {spec['display_name']} at {target}")

    return installed


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
