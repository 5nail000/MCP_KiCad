"""Workspace and environment configuration. Paths are discovered, not hardcoded in MCP JSON."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_workspace() -> Path:
    env = os.environ.get("KICAD_AI_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    # src/kicad_ai/config.py -> repo root is parents[2]
    here = Path(__file__).resolve()
    if here.parent.name == "kicad_ai" and here.parents[2].name:
        candidate = here.parents[2]
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd().resolve()


def load_env(workspace: Path | None = None) -> Path:
    root = workspace or get_workspace()
    _load_dotenv(root / ".env")
    os.environ.setdefault("KICAD_AI_WORKSPACE", str(root))
    return root


def get_log_level() -> str:
    return os.environ.get("KICAD_AI_LOG_LEVEL", "INFO")


def backup_keep() -> int:
    raw = os.environ.get("KICAD_AI_BACKUP_KEEP", "10")
    try:
        value = int(raw)
    except ValueError:
        return 10
    return max(1, value)


def env_override(name: str) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return Path(raw).expanduser()
