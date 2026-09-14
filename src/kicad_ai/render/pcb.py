"""2D PCB plots and 3D viewer captures via kicad-cli. No PCB → SKIPPED, not a fake image."""

from __future__ import annotations

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
from kicad_ai.render.config import RenderConfig, load_render_config
from kicad_ai.render.crop import crop_svg_file
from kicad_ai.render.models import scan_pcb_3d, scan_schematic_3d
from kicad_ai.render.raster import png_ok, svg_to_png
from kicad_ai.validate import resolve_kicad_files

TOP_LAYERS = "F.Cu,F.Paste,F.SilkS,F.Mask,F.CrtYd,Edge.Cuts"
BOTTOM_LAYERS = "B.Cu,B.Paste,B.SilkS,B.Mask,B.CrtYd,Edge.Cuts"
BOTH_LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"

SIDES = {
    "top": {"layers": TOP_LAYERS, "mirror": False},
    "bottom": {"layers": BOTTOM_LAYERS, "mirror": True},
    "both": {"layers": BOTH_LAYERS, "mirror": False},
}

CAMERAS = {
    "top": {"side": "top", "rotate": None},
    "bottom": {"side": "bottom", "rotate": None},
    "front": {"side": "front", "rotate": None},
    "isometric": {"side": "top", "rotate": "-45,0,45"},
}


def _require_pcb(user_path: str | Path) -> tuple[Path | None, dict[str, Any]]:
    files = resolve_kicad_files(user_path)
    pcb = files["pcb"]
    if pcb is None:
        return None, skipped(kind="pcb", reason="no .kicad_pcb in the KiCad project (board was never created)")
    return assert_allowed(pcb, write=False), files


def render_pcb(
    user_path: str | Path,
    *,
    side: str = "top",
    force: bool = False,
    quality: str | None = None,
    config: RenderConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_render_config()
    pcb, files_or_skip = _require_pcb(user_path)
    if pcb is None:
        payload = files_or_skip
        payload["side"] = side
        return payload
    side_name = (side or "top").lower()
    if side_name not in SIDES:
        return skipped(kind="pcb", reason=f"unknown PCB side {side_name!r}; use top|bottom|both")
    spec = SIDES[side_name]
    stem = pcb.stem
    out_dir = project_render_dir(stem) / "pcb"
    svg_path = out_dir / f"{side_name}.svg"
    png_path = out_dir / f"{side_name}.png"
    meta_path = out_dir / f"{side_name}.meta.json"
    source_hash = file_sha256(pcb)
    dpi = cfg.docs_dpi if quality != "preview" else cfg.preview_dpi
    params = {"side": side_name, "dpi": dpi, "theme": cfg.theme}
    logger = get_logger()
    if not force and can_reuse(read_json(meta_path), source_hash=source_hash, params=params, outputs=[svg_path, png_path]):
        logger.info("pcb 2D render reuse side=%s", side_name)
        return {
            "success": True,
            "ok": True,
            "skipped": False,
            "status": "PASS",
            "side": side_name,
            "reused": True,
            "source_hash": source_hash,
            "artifacts": [
                artifact(kind="pcb", fmt="svg", path=svg_path, reused=True),
                artifact(kind="pcb", fmt="png", path=png_path, reused=True),
            ],
            "warnings": [],
            "backend": "kicad_cli",
        }

    args = [
        "pcb",
        "export",
        "svg",
        "--mode-single",
        "--fit-page-to-board",
        "--exclude-drawing-sheet",
        "--page-size-mode",
        "2",
        "--layers",
        spec["layers"],
        "--output",
        str(svg_path),
        str(pcb),
    ]
    if spec["mirror"]:
        args.extend(["--mirror"])
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    run_kicad_cli(args, timeout=180)
    if not svg_path.is_file():
        produced = list(out_dir.glob("*.svg"))
        if not produced:
            raise FileNotFoundError(f"kicad-cli pcb export svg produced no SVG for {side_name}")
        produced[0].replace(svg_path)
    crop_svg_file(svg_path, margin_mm=min(cfg.margin_mm, 10.0))
    bg = "white" if cfg.pcb_background == "white" else "transparent"
    svg_to_png(svg_path, png_path, dpi=dpi, background=bg)
    write_json(meta_path, metadata(source=pcb, source_hash=source_hash, extra=params))
    logger.info("pcb 2D render side=%s svg=%s", side_name, svg_path)
    return {
        "success": True,
        "ok": True,
        "skipped": False,
        "status": "PASS",
        "side": side_name,
        "reused": False,
        "source_hash": source_hash,
        "artifacts": [
            artifact(kind="pcb", fmt="svg", path=svg_path),
            artifact(kind="pcb", fmt="png", path=png_path),
        ],
        "warnings": [],
        "backend": "kicad_cli",
    }


def render_pcb_3d(
    user_path: str | Path,
    *,
    camera: str = "isometric",
    force: bool = False,
    config: RenderConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_render_config()
    files = resolve_kicad_files(user_path)
    pcb = files["pcb"]
    sch = files["sch"]
    warnings: list[dict[str, Any]] = []
    if sch is not None:
        warnings.extend(scan_schematic_3d(sch))
    if pcb is None:
        payload = skipped(kind="pcb_3d", reason="no .kicad_pcb in the KiCad project (board was never created)")
        payload["camera"] = camera
        payload["warnings"] = [item["message"] for item in warnings]
        return payload
    pcb = assert_allowed(pcb, write=False)
    warnings.extend(scan_pcb_3d(pcb))
    cam_name = (camera or "isometric").lower()
    if cam_name not in CAMERAS:
        return skipped(kind="pcb_3d", reason=f"unknown camera {cam_name!r}; use top|bottom|front|isometric")
    spec = CAMERAS[cam_name]
    stem = pcb.stem
    png_path = project_render_dir(stem) / "3d" / f"{cam_name}.png"
    meta_path = project_render_dir(stem) / "3d" / f"{cam_name}.meta.json"
    source_hash = file_sha256(pcb)
    bg = cfg.pcb_background
    if bg == "white":
        bg_flag = "opaque"
    else:
        bg_flag = "transparent"
    params = {
        "camera": cam_name,
        "background": bg_flag,
        "quality": cfg.pcb_quality,
        "width": cfg.pcb_width,
        "height": cfg.pcb_height,
    }
    logger = get_logger()
    if not force and can_reuse(read_json(meta_path), source_hash=source_hash, params=params, outputs=[png_path]):
        logger.info("pcb 3D render reuse camera=%s", cam_name)
        return {
            "success": True,
            "ok": True,
            "skipped": False,
            "status": "PASS",
            "camera": cam_name,
            "reused": True,
            "source_hash": source_hash,
            "artifacts": [artifact(kind="pcb_3d", fmt="png", path=png_path, reused=True)],
            "warnings": [item["message"] for item in warnings],
            "backend": "kicad_cli",
        }

    args = [
        "pcb",
        "render",
        "--output",
        str(png_path),
        "--width",
        str(cfg.pcb_width),
        "--height",
        str(cfg.pcb_height),
        "--side",
        spec["side"],
        "--background",
        bg_flag,
        "--quality",
        cfg.pcb_quality,
        str(pcb),
    ]
    if spec["rotate"]:
        args.extend(["--rotate", spec["rotate"]])
        args.append("--perspective")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    run_kicad_cli(args, timeout=300)
    if not png_path.is_file() or not png_ok(png_path):
        raise FileNotFoundError(f"kicad-cli pcb render did not write a PNG for camera {cam_name}")
    write_json(meta_path, metadata(source=pcb, source_hash=source_hash, extra=params))
    logger.info("pcb 3D render camera=%s png=%s warnings=%s", cam_name, png_path, len(warnings))
    return {
        "success": True,
        "ok": True,
        "skipped": False,
        "status": "PASS",
        "camera": cam_name,
        "reused": False,
        "source_hash": source_hash,
        "artifacts": [artifact(kind="pcb_3d", fmt="png", path=png_path)],
        "warnings": [item["message"] for item in warnings],
        "backend": "kicad_cli",
    }
