"""Whitelist project paths so the MCP cannot write outside the workspace."""

from __future__ import annotations

from pathlib import Path

from kicad_ai.config import get_workspace


class PathDenied(PermissionError):
    """Raised when a requested path is outside the allowed workspace trees."""


WRITE_ROOTS = ("projects", "backups", "logs", "docs", "components")
READ_ROOTS = WRITE_ROOTS + ("src", "tests", "scripts", "tools")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_in_workspace(user_path: str | Path, *, workspace: Path | None = None) -> Path:
    root = (workspace or get_workspace()).resolve()
    path = Path(user_path)
    if not path.is_absolute():
        path = root / path
    resolved = path.expanduser().resolve()
    if not _is_relative_to(resolved, root):
        raise PathDenied(f"Path is outside workspace: {resolved}")
    return resolved


def assert_allowed(
    user_path: str | Path,
    *,
    write: bool = False,
    workspace: Path | None = None,
) -> Path:
    root = (workspace or get_workspace()).resolve()
    resolved = resolve_in_workspace(user_path, workspace=root)
    allowed = WRITE_ROOTS if write else READ_ROOTS
    if any(_is_relative_to(resolved, root / name) for name in allowed):
        return resolved
    # Allow the workspace root itself only for reads (mcp.json / doctor).
    if not write and resolved == root:
        return resolved
    kind = "write" if write else "read"
    raise PathDenied(f"{kind} denied for path outside allowed directories: {resolved}")


def project_root_for(path: Path, *, workspace: Path | None = None) -> Path:
    """Return the KiCad project directory (folder that contains .kicad_pro/.kicad_sch)."""
    root = (workspace or get_workspace()).resolve()
    resolved = path if path.is_absolute() else resolve_in_workspace(path, workspace=root)
    if resolved.is_file():
        resolved = resolved.parent
    projects = root / "projects"
    if _is_relative_to(resolved, projects) and resolved != projects:
        # Keep backups keyed by the leaf project folder, not examples/user.
        return resolved
    return resolved


def find_lock_files(project_dir: Path) -> list[Path]:
    locks: list[Path] = []
    if not project_dir.is_dir():
        return locks
    for pattern in ("*.lck", "~*.lck", "~*.kicad_sch", "~*.kicad_pcb"):
        locks.extend(project_dir.glob(pattern))
    return sorted({p.resolve() for p in locks})
