"""Inspect footprint 3D models. Missing models are warnings, never a hard render error."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger

_MODEL_RE = re.compile(r'\(model\s+"([^"]+)"')
_FP_RE = re.compile(r'\(footprint\s+"([^"]+)"')
_LIB_ID_RE = re.compile(r'\(lib_id\s+"([^"]+)"')
_REF_RE = re.compile(r'\(property\s+"Reference"\s+"([^"]+)"')
_FOOTPRINT_PROP_RE = re.compile(r'\(property\s+"Footprint"\s+"([^"]+)"')


def expand_model_path(raw: str) -> Path:
    expanded = raw.strip()
    for match in re.findall(r"\$\{([^}]+)\}", expanded):
        value = os.environ.get(match, "")
        expanded = expanded.replace("${" + match + "}", value)
    return Path(expanded)


def model_exists(raw: str) -> bool:
    path = expand_model_path(raw)
    if path.is_file():
        return True
    for suffix in (".wrl", ".step", ".stp", ".stpz", ".WRL", ".STEP"):
        candidate = path.with_suffix(suffix)
        if candidate.is_file():
            return True
        if path.with_name(path.name + suffix).is_file():
            return True
    return False


def models_in_text(text: str) -> list[str]:
    return _MODEL_RE.findall(text)


def footprint_model_paths(lib_id: str) -> list[str]:
    """Look up 3D models from the official KiCad footprint library."""
    if ":" not in lib_id:
        return []
    library, name = lib_id.split(":", 1)
    install = require_kicad()
    pretty = install.footprint_dir / f"{library}.pretty" / f"{name}.kicad_mod"
    if not pretty.is_file():
        return []
    return models_in_text(pretty.read_text(encoding="utf-8", errors="replace"))


def scan_schematic_3d(schematic: Path) -> list[dict[str, Any]]:
    text = schematic.read_text(encoding="utf-8", errors="replace")
    warnings: list[dict[str, Any]] = []
    # Split loosely on symbol blocks.
    blocks = re.split(r"\(symbol\s+", text)[1:]
    logger = get_logger()
    for block in blocks:
        refs = _REF_RE.findall(block)
        if not refs:
            continue
        ref = refs[0]
        if ref.startswith("#"):
            continue
        if not re.match(r"^[A-Za-z]{1,6}\d+", ref):
            continue
        footprints = _FOOTPRINT_PROP_RE.findall(block)
        if not footprints or not footprints[0]:
            warnings.append({"ref": ref, "message": f"{ref}: no footprint assigned (3D model not found)"})
            continue
        fp = footprints[0]
        models = footprint_model_paths(fp)
        if not models:
            warnings.append({"ref": ref, "message": f"{ref}: 3D model not found ({fp})"})
            continue
        missing = [item for item in models if not model_exists(item)]
        if missing:
            warnings.append({"ref": ref, "message": f"{ref}: 3D model not found ({missing[0]})"})
    if warnings:
        logger.warning("3D render warning: %s missing 3D models", len(warnings))
        for item in warnings:
            logger.warning("  %s", item["message"])
    return warnings


def scan_pcb_3d(pcb: Path) -> list[dict[str, Any]]:
    text = pcb.read_text(encoding="utf-8", errors="replace")
    warnings: list[dict[str, Any]] = []
    footprints = re.split(r"\(footprint\s+", text)[1:]
    for block in footprints:
        refs = re.findall(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        ref = refs[0] if refs else "?"
        models = models_in_text(block)
        if not models:
            warnings.append({"ref": ref, "message": f"{ref}: 3D model not found"})
            continue
        missing = [item for item in models if not model_exists(item)]
        if missing:
            warnings.append({"ref": ref, "message": f"{ref}: 3D model not found ({missing[0]})"})
    return warnings
