"""Optional SKiDL layer. KiCad files under projects/ stay the source of truth.

SKiDL must not overwrite existing .kicad_sch / .kicad_pcb / .kicad_pro.
Generated artefacts are allowed only under skidl_lab/generated/.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

from kicad_ai.config import get_workspace
from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import PathDenied, assert_allowed

_configured = False


def generated_dir() -> Path:
    path = get_workspace() / "skidl_lab" / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_lab_importable() -> None:
    root = str(get_workspace())
    if root not in sys.path:
        sys.path.insert(0, root)


def configure() -> Any:
    """Point SKiDL at KiCad 10 libraries. Safe to call repeatedly. Lazy-imports skidl."""
    global _configured
    install = require_kicad()
    symbol_dir = str(install.symbol_dir)
    for key in (
        "KICAD_SYMBOL_DIR",
        "KICAD5_SYMBOL_DIR",
        "KICAD6_SYMBOL_DIR",
        "KICAD7_SYMBOL_DIR",
        "KICAD8_SYMBOL_DIR",
        "KICAD9_SYMBOL_DIR",
        "KICAD10_SYMBOL_DIR",
    ):
        os.environ.setdefault(key, symbol_dir)
    _ensure_lab_importable()
    import skidl
    from skidl import KICAD10, lib_search_paths, set_default_tool

    set_default_tool(KICAD10)
    symbol_dir = str(install.symbol_dir)
    paths = lib_search_paths[KICAD10]
    if symbol_dir not in paths:
        paths.append(symbol_dir)
    if not _configured:
        get_logger().info("SKiDL %s tool=KICAD10 symbols=%s", getattr(skidl, "__version__", "?"), symbol_dir)
        _configured = True
    return skidl


def new_circuit():
    configure()
    from skidl import Circuit

    circuit = Circuit()
    circuit.no_files = True
    return circuit


def list_blocks() -> list[str]:
    configure()
    from skidl_lab.blocks import BLOCKS

    return sorted(BLOCKS)


def get_block(name: str) -> Callable[..., Any]:
    configure()
    from skidl_lab.blocks import BLOCKS

    try:
        return BLOCKS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown SKiDL block {name!r}. Known: {sorted(BLOCKS)}") from exc


def erc_circuit(circuit: Any) -> dict[str, Any]:
    configure()
    from skidl import erc_logger

    circuit.no_files = True
    captured = _CaptureHandler()
    erc_logger.addHandler(captured)
    try:
        circuit.ERC()
        errors = int(erc_logger.error.count)
        warnings = int(erc_logger.warning.count)
    finally:
        erc_logger.removeHandler(captured)

    ok = errors == 0 and warnings == 0
    parts = []
    nets = []
    for part in getattr(circuit, "parts", []):
        parts.append(getattr(part, "ref", None))
    for net in getattr(circuit, "nets", []):
        pins = [str(pin) for pin in getattr(net, "pins", [])]
        if pins:
            nets.append({"name": getattr(net, "name", None), "pins": pins})
    return {
        "success": True,
        "ok": ok,
        "skipped": False,
        "status": "PASS" if ok else "FAIL",
        "engine": "skidl ERC",
        "errors": errors,
        "warnings": warnings,
        "messages": captured.messages,
        "parts": parts,
        "nets": nets,
        "writes_kicad_schematic": False,
    }


def run_block_erc(name: str) -> dict[str, Any]:
    circuit = get_block(name)()
    result = erc_circuit(circuit)
    result["block"] = name
    get_logger().info("SKiDL ERC block=%s status=%s errors=%s warnings=%s", name, result["status"], result["errors"], result["warnings"])
    return result


def export_block_netlist(name: str, dest: str | Path | None = None) -> dict[str, Any]:
    configure()
    from skidl import KICAD10

    target = Path(dest) if dest else generated_dir() / f"{name}.net"
    target = assert_allowed(target, write=True)
    _assert_skidl_output_allowed(target)
    circuit = get_block(name)()
    circuit.no_files = False
    text = circuit.generate_netlist(file_=str(target), tool=KICAD10, do_backup=False)
    circuit.no_files = True
    get_logger().info("SKiDL netlist block=%s path=%s", name, target)
    return {
        "success": True,
        "block": name,
        "path": str(target),
        "preview": "\n".join(str(text).splitlines()[:40]),
        "note": "Generated under skidl_lab/generated/. This is not the KiCad project schematic.",
    }


def _assert_skidl_output_allowed(path: Path) -> None:
    root = get_workspace().resolve()
    resolved = path.resolve()
    generated = (root / "skidl_lab" / "generated").resolve()
    projects = (root / "projects").resolve()
    try:
        resolved.relative_to(projects)
    except ValueError:
        pass
    else:
        raise PathDenied("SKiDL must not write into projects/ (KiCad remains the source of truth)")
    try:
        resolved.relative_to(generated)
    except ValueError as exc:
        raise PathDenied(f"SKiDL output may only be written under {generated}") from exc
    if resolved.suffix in {".kicad_sch", ".kicad_pcb", ".kicad_pro"}:
        raise PathDenied(
            "SKiDL must not emit .kicad_sch/.kicad_pcb/.kicad_pro. "
            "Export a netlist under skidl_lab/generated/ instead."
        )


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())
