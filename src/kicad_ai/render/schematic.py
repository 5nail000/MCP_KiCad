"""Schematic renders from kicad-cli sch export svg/pdf. PNG is rasterized from that SVG."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from kicad_ai.kicad_cli import run_kicad_cli
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed
from kicad_ai.render.common import (
    artifact,
    can_reuse,
    file_sha256,
    metadata,
    project_render_dir,
    read_json,
    skipped,
    write_json,
)
from kicad_ai.render.config import RenderConfig, SchematicView, load_render_config, resolve_dpi
from kicad_ai.render.crop import apply_dark_presentation, crop_svg_file
from kicad_ai.render.raster import svg_to_png
from kicad_ai.validate import resolve_kicad_files


def _xy(pos: object) -> tuple[float, float]:
    if hasattr(pos, "x") and hasattr(pos, "y"):
        return float(pos.x), float(pos.y)
    if isinstance(pos, dict) and "x" in pos and "y" in pos:
        return float(pos["x"]), float(pos["y"])
    if isinstance(pos, (tuple, list)) and len(pos) >= 2:
        return float(pos[0]), float(pos[1])
    raise TypeError(f"unsupported position: {type(pos)!r}")


def _component_boxes(schematic: Path) -> dict[str, tuple[float, float]]:
    import kicad_sch_api as ksa

    sch = ksa.load_schematic(str(schematic))
    boxes: dict[str, tuple[float, float]] = {}
    for component in getattr(sch, "components", []) or []:
        ref = getattr(component, "reference", None)
        pos = getattr(component, "position", None)
        if not ref or pos is None:
            continue
        boxes[str(ref)] = _xy(pos)
    return boxes


def _view_clip(schematic: Path, view: SchematicView, margin_mm: float) -> tuple[float, float, float, float] | None:
    if not view.references:
        return None
    boxes = _component_boxes(schematic)
    points = [boxes[ref] for ref in view.references if ref in boxes]
    if not points:
        return None
    pad = view.padding_mm if view.padding_mm is not None else max(margin_mm, 20.0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    # Symbol body around the origin (~15mm) plus padding.
    body = 15.0
    return min(xs) - body - pad, min(ys) - body - pad, max(xs) + body + pad, max(ys) + body + pad


def render_schematic(
    user_path: str | Path,
    *,
    view: str = "full",
    theme: str | None = None,
    quality: str | None = None,
    force: bool = False,
    config: RenderConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_render_config()
    files = resolve_kicad_files(user_path)
    sch = files["sch"]
    if sch is None:
        return skipped(kind="schematic", reason="no .kicad_sch")
    sch = assert_allowed(sch, write=False)
    stem = sch.stem
    out_dir = project_render_dir(stem)
    view_name = (view or "full").strip() or "full"
    dpi = resolve_dpi(cfg, quality)
    theme_name = (theme or cfg.theme).lower()
    logger = get_logger()

    svg_path = out_dir / "schematic" / f"{view_name}.svg"
    png_path = out_dir / "schematic" / f"{view_name}.png"
    pdf_path = out_dir / "schematic" / f"{view_name}.pdf"
    meta_path = out_dir / "schematic" / f"{view_name}.meta.json"
    source_hash = file_sha256(sch)
    params = {"view": view_name, "theme": theme_name, "dpi": dpi, "margin_mm": cfg.margin_mm}

    clip = None
    selected: SchematicView | None = None
    if view_name != "full":
        for item in cfg.views:
            if item.name == view_name:
                selected = item
                break
        if selected is None:
            return skipped(kind="schematic", reason=f"unknown schematic view {view_name!r}")
        clip = _view_clip(sch, selected, cfg.margin_mm)
        if clip is None:
            return skipped(
                kind="schematic",
                reason=f"view {view_name!r}: none of {list(selected.references)} are on this schematic",
            )

    if not force and can_reuse(read_json(meta_path), source_hash=source_hash, params=params, outputs=[svg_path, png_path]):
        logger.info("schematic render reuse view=%s hash=%s", view_name, source_hash[:12])
        artifacts = [
            artifact(kind="schematic", fmt="svg", path=svg_path, reused=True),
            artifact(kind="schematic", fmt="png", path=png_path, reused=True),
        ]
        if pdf_path.is_file():
            artifacts.append(artifact(kind="schematic", fmt="pdf", path=pdf_path, reused=True))
        return {
            "success": True,
            "ok": True,
            "skipped": False,
            "status": "PASS",
            "view": view_name,
            "theme": theme_name,
            "dpi": dpi,
            "reused": True,
            "source_hash": source_hash,
            "artifacts": artifacts,
            "warnings": [],
            "backend": "kicad_cli",
        }

    tmp = out_dir / "schematic" / "_kicad_svg"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    svg_args = [
        "sch",
        "export",
        "svg",
        "--exclude-drawing-sheet",
        "--no-background-color",
        "--output",
        str(tmp),
        str(sch),
    ]
    run_kicad_cli(svg_args, timeout=180)
    produced = list(tmp.glob("*.svg"))
    if not produced:
        raise FileNotFoundError(f"kicad-cli sch export svg produced no SVG in {tmp}")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced[0], svg_path)
    shutil.rmtree(tmp, ignore_errors=True)

    crop_svg_file(svg_path, margin_mm=cfg.margin_mm, clip=clip)
    if theme_name == "dark":
        text = svg_path.read_text(encoding="utf-8", errors="replace")
        svg_path.write_text(apply_dark_presentation(text), encoding="utf-8")

    svg_to_png(svg_path, png_path, dpi=dpi, background="white" if theme_name == "light" else "transparent")

    pdf_args = [
        "sch",
        "export",
        "pdf",
        "--exclude-drawing-sheet",
        "--no-background-color",
        "--output",
        str(pdf_path),
        str(sch),
    ]
    run_kicad_cli(pdf_args, timeout=180)

    meta = metadata(source=sch, source_hash=source_hash, extra=params)
    write_json(meta_path, meta)
    logger.info("schematic render view=%s svg=%s png=%s", view_name, svg_path, png_path)
    return {
        "success": True,
        "ok": True,
        "skipped": False,
        "status": "PASS",
        "view": view_name,
        "theme": theme_name,
        "dpi": dpi,
        "reused": False,
        "source_hash": source_hash,
        "artifacts": [
            artifact(kind="schematic", fmt="svg", path=svg_path),
            artifact(kind="schematic", fmt="png", path=png_path),
            artifact(kind="schematic", fmt="pdf", path=pdf_path),
        ],
        "warnings": [],
        "backend": "kicad_cli",
    }


def list_schematic_views(user_path: str | Path, *, config: RenderConfig | None = None) -> dict[str, Any]:
    cfg = config or load_render_config()
    files = resolve_kicad_files(user_path)
    sch = files["sch"]
    available = [{"name": "full", "description": "Entire schematic"}]
    if sch is None:
        return {"success": True, "views": available}
    boxes = _component_boxes(sch)
    for item in cfg.views:
        hits = [ref for ref in item.references if ref in boxes]
        available.append(
            {
                "name": item.name,
                "description": item.description,
                "references": list(item.references),
                "present": hits,
                "available": bool(hits),
            }
        )
    return {"success": True, "views": available}
