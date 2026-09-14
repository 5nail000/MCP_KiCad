"""Search official KiCad symbol libraries without inventing part numbers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger

_TOP_LEVEL_SYMBOL = re.compile(r'(?m)^\t\(symbol "([^"]+)"')
_UNIT_SUFFIX = re.compile(r"_\d+_\d+$")


def _symbol_dir() -> Path:
    return require_kicad().symbol_dir


def list_libraries() -> list[str]:
    directory = _symbol_dir()
    names = [p.stem for p in sorted(directory.glob("*.kicad_sym"))]
    get_logger().info("Found %s symbol libraries in %s", len(names), directory)
    return names


def parse_library_symbols(library_file: Path) -> list[str]:
    text = library_file.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    for name in _TOP_LEVEL_SYMBOL.findall(text):
        if _UNIT_SUFFIX.search(name):
            continue
        names.append(name)
    return names


def search_symbols(query: str, *, library: str | None = None, limit: int = 40) -> list[dict[str, Any]]:
    """Substring search over real KiCad 10 library files."""
    if not query or not query.strip():
        raise ValueError("search query must not be empty")
    needle = query.strip().lower()
    symbol_dir = _symbol_dir()
    files = [symbol_dir / f"{library}.kicad_sym"] if library else sorted(symbol_dir.glob("*.kicad_sym"))
    results: list[dict[str, Any]] = []
    for lib_file in files:
        if not lib_file.is_file():
            continue
        lib_name = lib_file.stem
        for name in parse_library_symbols(lib_file):
            lib_id = f"{lib_name}:{name}"
            haystack = f"{lib_id} {name}".lower()
            if needle not in haystack:
                continue
            results.append({"lib_id": lib_id, "library": lib_name, "name": name})
            if len(results) >= limit:
                return results
    return results


def symbol_info(lib_id: str) -> dict[str, Any]:
    """Exact lookup via kicad-sch-api against the official KiCad libraries."""
    import kicad_sch_api as ksa

    require_kicad()
    info = ksa.get_symbol_info(lib_id)
    if info is None:
        raise FileNotFoundError(f"Symbol not found in KiCad libraries: {lib_id}")
    pins = []
    for pin in getattr(info, "pins", []) or []:
        pins.append(
            {
                "number": getattr(pin, "number", None),
                "name": getattr(pin, "name", None),
                "type": str(getattr(pin, "pin_type", "")),
            }
        )
    return {
        "lib_id": getattr(info, "lib_id", lib_id),
        "name": getattr(info, "name", lib_id.split(":")[-1]),
        "library": getattr(info, "library", lib_id.split(":")[0]),
        "description": getattr(info, "description", "") or "",
        "keywords": getattr(info, "keywords", "") or "",
        "datasheet": getattr(info, "datasheet", "") or "",
        "reference_prefix": getattr(info, "reference_prefix", ""),
        "power_symbol": bool(getattr(info, "power_symbol", False)),
        "pins": pins,
    }
