import os, re, zipfile, tempfile, shutil
from datetime import datetime
from pathlib import Path
from typing import List

BACKUP_DIR = Path("backups")
EXCLUDE_DIRS = {"backups", "logs", ".git", "__pycache__", ".pythonlibs", ".venv", "venv", ".mypy_cache"}
EXCLUDE_FILES = {".DS_Store"}

def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def _sanitize(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", label or "auto")

def ensure_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def create_backup(label: str = "auto") -> str:
    ensure_dir()
    name = f"{_ts()}_{_sanitize(label)}.zip"
    archive_path = BACKUP_DIR / name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        root = Path(".").resolve()
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if not rel.parts:
                continue
            if rel.parts[0] in EXCLUDE_DIRS:
                continue
            if rel.name in EXCLUDE_FILES:
                continue
            if path.is_file():
                zf.write(path, arcname=str(rel))
    return name

def list_backups(limit: int = 50) -> List[str]:
    ensure_dir()
    files = sorted((p.name for p in BACKUP_DIR.glob("*.zip")), reverse=True)
    return files[:limit]

def restore_backup(name: str) -> str:
    ensure_dir()
    src = BACKUP_DIR / name
    if not src.exists():
        raise FileNotFoundError(f"Backup not found: {name}")
    # Extract to a temp dir first, then copy over to avoid half-written state
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(td)
        temp_root = Path(td)
        for item in temp_root.rglob("*"):
            rel = item.relative_to(temp_root)
            target = Path(".") / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
    return name

def prune_backups(max_keep: int = 20) -> None:
    ensure_dir()
    files = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    for old in files[max_keep:]:
        try:
            old.unlink()
        except Exception:
            pass