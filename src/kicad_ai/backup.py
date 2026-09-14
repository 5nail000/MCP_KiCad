"""Project file backups with timestamped folders and retention."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from kicad_ai.config import backup_keep, get_workspace
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed, project_root_for

KEEP_FILES = (
    ".kicad_pro",
    ".kicad_sch",
    ".kicad_pcb",
    ".kicad_sym",
    ".kicad_mod",
    "sym-lib-table",
    "fp-lib-table",
    ".csv",
    ".md",
    ".net",
    ".json",
)


def backups_root(workspace: Path | None = None) -> Path:
    root = (workspace or get_workspace()) / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def backup_project(target: str | Path, *, keep: int | None = None) -> Path:
    logger = get_logger()
    workspace = get_workspace()
    path = assert_allowed(target, write=False, workspace=workspace)
    project_dir = project_root_for(path, workspace=workspace)
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory does not exist: {project_dir}")

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = backups_root(workspace) / project_dir.name / stamp
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest = backups_root(workspace) / project_dir.name / f"{stamp}_{datetime.now().microsecond}"
    dest.mkdir(parents=True, exist_ok=False)

    copied = 0
    for item in project_dir.iterdir():
        if item.name in {".git"}:
            continue
        if item.is_dir():
            shutil.copytree(item, dest / item.name, dirs_exist_ok=False)
            copied += 1
            continue
        if item.suffix in KEEP_FILES or item.name in KEEP_FILES or item.suffix.startswith(".kicad"):
            shutil.copy2(item, dest / item.name)
            copied += 1
            continue
        if item.suffix.lower() in {".csv", ".md", ".net", ".json", ".pdf", ".txt"}:
            shutil.copy2(item, dest / item.name)
            copied += 1

    logger.info("Backup created: %s (%s files/dirs from %s)", dest, copied, project_dir)
    prune_backups(project_dir.name, keep=keep if keep is not None else backup_keep())
    return dest


def list_backups(project_name: str) -> list[Path]:
    folder = backups_root() / project_name
    if not folder.is_dir():
        return []
    return sorted([p for p in folder.iterdir() if p.is_dir()], reverse=True)


def prune_backups(project_name: str, *, keep: int) -> list[Path]:
    logger = get_logger()
    existing = list_backups(project_name)
    removed: list[Path] = []
    for stale in existing[keep:]:
        shutil.rmtree(stale, ignore_errors=False)
        removed.append(stale)
        logger.info("Pruned old backup: %s", stale)
    return removed


def restore_backup(project_dir: str | Path, backup_dir: str | Path) -> Path:
    logger = get_logger()
    workspace = get_workspace()
    dest = project_root_for(assert_allowed(project_dir, write=True, workspace=workspace), workspace=workspace)
    source = assert_allowed(backup_dir, write=False, workspace=workspace)
    if not source.is_dir():
        raise FileNotFoundError(f"Backup not found: {source}")
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    logger.info("Restored backup %s -> %s", source, dest)
    return dest
