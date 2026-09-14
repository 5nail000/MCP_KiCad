"""Discover KiCad 10 executables and official symbol/footprint libraries."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kicad_ai.config import env_override


@dataclass(frozen=True)
class KiCadInstall:
    version: str
    root: Path
    kicad_exe: Path
    kicad_cli: Path
    symbol_dir: Path
    footprint_dir: Path
    template_dir: Path


def _program_files() -> list[Path]:
    paths: list[Path] = []
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        value = os.environ.get(key)
        if value:
            paths.append(Path(value))
    paths.append(Path(r"C:\Program Files"))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def _parse_version_from_path(root: Path) -> str:
    return root.name


def _looks_like_install(root: Path) -> bool:
    return (root / "bin" / "kicad.exe").is_file() and (root / "bin" / "kicad-cli.exe").is_file()


def find_kicad() -> KiCadInstall | None:
    exe_override = env_override("KICAD_EXE")
    cli_override = env_override("KICAD_CLI")
    symbol_override = env_override("KICAD_SYMBOL_DIR")
    footprint_override = env_override("KICAD_FOOTPRINT_DIR")

    root: Path | None = None
    if exe_override and exe_override.is_file():
        root = exe_override.parent.parent
    else:
        candidates: list[Path] = []
        for pf in _program_files():
            base = pf / "KiCad"
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir(), reverse=True):
                if child.is_dir() and _looks_like_install(child):
                    candidates.append(child)
        if candidates:
            # Prefer 10.x if several versions exist.
            ten = [c for c in candidates if c.name.startswith("10")]
            root = ten[0] if ten else candidates[0]

    if root is None or not _looks_like_install(root):
        return None

    kicad_exe = exe_override if exe_override and exe_override.is_file() else root / "bin" / "kicad.exe"
    kicad_cli = cli_override if cli_override and cli_override.is_file() else root / "bin" / "kicad-cli.exe"
    symbol_dir = (
        symbol_override
        if symbol_override and symbol_override.is_dir()
        else root / "share" / "kicad" / "symbols"
    )
    footprint_dir = (
        footprint_override
        if footprint_override and footprint_override.is_dir()
        else root / "share" / "kicad" / "footprints"
    )
    template_dir = root / "share" / "kicad" / "template"
    version = probe_version(kicad_cli) or _parse_version_from_path(root)
    if not kicad_exe.is_file() or not kicad_cli.is_file():
        return None
    return KiCadInstall(
        version=version,
        root=root,
        kicad_exe=kicad_exe,
        kicad_cli=kicad_cli,
        symbol_dir=symbol_dir,
        footprint_dir=footprint_dir,
        template_dir=template_dir,
    )


def probe_version(kicad_cli: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(kicad_cli), "version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


def apply_library_env(install: KiCadInstall) -> None:
    """Point kicad-sch-api and KiCad itself at the official libraries."""
    os.environ.setdefault("KICAD_SYMBOL_DIR", str(install.symbol_dir))
    os.environ.setdefault("KICAD_FOOTPRINT_DIR", str(install.footprint_dir))
    os.environ.setdefault("KICAD10_SYMBOL_DIR", str(install.symbol_dir))
    os.environ.setdefault("KICAD10_FOOTPRINT_DIR", str(install.footprint_dir))
    bin_dir = str(install.kicad_exe.parent)
    path = os.environ.get("PATH", "")
    if bin_dir.lower() not in path.lower():
        os.environ["PATH"] = bin_dir + os.pathsep + path


def require_kicad() -> KiCadInstall:
    install = find_kicad()
    if install is None:
        raise FileNotFoundError(
            "KiCad executable not found. Install KiCad 10.x or set KICAD_EXE / KICAD_CLI in .env"
        )
    apply_library_env(install)
    return install
