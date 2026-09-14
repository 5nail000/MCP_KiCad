"""Shared helpers for KiCad-derived renders (hash, paths, artifacts)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kicad_ai import __version__
from kicad_ai.config import get_workspace
from kicad_ai.paths import assert_allowed

RENDERER_NAME = "kicad_cli"


def renders_root(workspace: Path | None = None) -> Path:
    root = (workspace or get_workspace()) / "renders"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_render_dir(project_stem: str, workspace: Path | None = None) -> Path:
    path = renders_root(workspace) / project_stem
    (path / "schematic").mkdir(parents=True, exist_ok=True)
    (path / "pcb").mkdir(parents=True, exist_ok=True)
    (path / "3d").mkdir(parents=True, exist_ok=True)
    return path


def relpath(path: Path, workspace: Path | None = None) -> str:
    root = (workspace or get_workspace()).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    dest = assert_allowed(path, write=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def metadata(
    *,
    source: Path,
    source_hash: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": relpath(source),
        "source_hash": source_hash,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "renderer_version": __version__,
        "backend": RENDERER_NAME,
    }
    if extra:
        payload.update(extra)
    return payload


def artifact(*, kind: str, fmt: str, path: Path, reused: bool = False) -> dict[str, Any]:
    return {
        "type": kind,
        "format": fmt,
        "path": relpath(path),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "reused": reused,
    }


def skipped(*, kind: str, reason: str) -> dict[str, Any]:
    return {
        "success": True,
        "ok": True,
        "skipped": True,
        "status": "SKIPPED",
        "type": kind,
        "reason": reason,
        "artifacts": [],
        "warnings": [],
        "backend": RENDERER_NAME,
    }


def can_reuse(meta: dict[str, Any] | None, *, source_hash: str, params: dict[str, Any], outputs: list[Path]) -> bool:
    if not meta:
        return False
    if meta.get("source_hash") != source_hash:
        return False
    if meta.get("backend") != RENDERER_NAME:
        return False
    for key, value in params.items():
        if meta.get(key) != value:
            return False
    return all(path.is_file() and path.stat().st_size > 0 for path in outputs)
