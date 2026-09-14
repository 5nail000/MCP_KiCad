"""Orchestrate schematic + PCB 2D + PCB 3D renders into a project report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kicad_ai.config import get_workspace
from kicad_ai.logging_setup import get_logger
from kicad_ai.render.common import project_render_dir, relpath, skipped, write_json
from kicad_ai.render.config import load_render_config
from kicad_ai.render.pcb import CAMERAS, SIDES, render_pcb, render_pcb_3d
from kicad_ai.render.schematic import list_schematic_views, render_schematic
from kicad_ai.validate import resolve_kicad_files


def render_project(
    user_path: str | Path,
    *,
    theme: str | None = None,
    quality: str | None = None,
    force: bool = False,
    include_views: bool = True,
) -> dict[str, Any]:
    cfg = load_render_config()
    files = resolve_kicad_files(user_path)
    logger = get_logger()
    warnings: list[str] = []
    artifacts: list[dict[str, Any]] = []
    sections: dict[str, Any] = {}

    if files["sch"] is None:
        sch_full = skipped(kind="schematic", reason="no .kicad_sch")
    else:
        sch_full = render_schematic(user_path, view="full", theme=theme, quality=quality, force=force, config=cfg)
        if include_views:
            listing = list_schematic_views(user_path, config=cfg)
            for item in listing.get("views") or []:
                name = item.get("name")
                if name in {None, "full"} or not item.get("available"):
                    continue
                extra = render_schematic(
                    user_path, view=str(name), theme=theme, quality=quality, force=force, config=cfg
                )
                artifacts.extend(extra.get("artifacts") or [])
                warnings.extend(extra.get("warnings") or [])
                sections[f"schematic_{name}"] = extra
    artifacts.extend(sch_full.get("artifacts") or [])
    warnings.extend(sch_full.get("warnings") or [])
    sections["schematic"] = sch_full

    pcb_section: dict[str, Any] = {}
    if files["pcb"] is None:
        pcb_skip = skipped(kind="pcb", reason="no .kicad_pcb in the KiCad project (board was never created)")
        pcb_section = {side: pcb_skip for side in SIDES}
        sections["pcb"] = pcb_skip
        three_d = {cam: skipped(kind="pcb_3d", reason=pcb_skip["reason"]) for cam in CAMERAS}
        probe = render_pcb_3d(user_path, camera="top", force=force, config=cfg)
        warnings.extend(probe.get("warnings") or [])
        sections["pcb_3d"] = probe
    else:
        for side in SIDES:
            result = render_pcb(user_path, side=side, force=force, quality=quality, config=cfg)
            pcb_section[side] = result
            artifacts.extend(result.get("artifacts") or [])
            warnings.extend(result.get("warnings") or [])
        sections["pcb"] = pcb_section
        three_d = {}
        for camera in CAMERAS:
            result = render_pcb_3d(user_path, camera=camera, force=force, config=cfg)
            three_d[camera] = result
            artifacts.extend(result.get("artifacts") or [])
            warnings.extend(result.get("warnings") or [])
        sections["pcb_3d"] = three_d

    blocking = []
    for item in (sch_full, *pcb_section.values(), *three_d.values()):
        if not item.get("skipped") and not item.get("ok"):
            blocking.append(item)
    verdict = "FAIL" if blocking else "PASS"
    stem = (files["sch"] or files["pro"] or files["project_dir"]).stem if files["sch"] or files["pro"] else "project"
    report = {
        "result": verdict,
        "success": True,
        "ok": verdict == "PASS",
        "status": verdict,
        "backend": "kicad_cli",
        "files": {key: (relpath(value) if value else None) for key, value in files.items()},
        "schematic": _paths_by_format(sch_full.get("artifacts") or []),
        "pcb": {
            side: _paths_by_format((pcb_section.get(side) or {}).get("artifacts") or [])
            for side in SIDES
        },
        "pcb_3d": {
            cam: _paths_by_format((three_d.get(cam) or {}).get("artifacts") or [])
            for cam in CAMERAS
        },
        "warnings": warnings,
        "artifacts": artifacts,
        "sections": {key: _slim(value) for key, value in sections.items()},
    }
    dest = project_render_dir(stem) / "render_report.json"
    write_json(dest, {k: v for k, v in report.items() if k != "sections"})
    latest = get_workspace() / "renders" / "render_report.json"
    write_json(latest, {k: v for k, v in report.items() if k != "sections"})
    report["report"] = relpath(dest)
    logger.info("render_project verdict=%s report=%s warnings=%s", verdict, dest, len(warnings))
    return report


def get_render_report(user_path: str | Path | None = None) -> dict[str, Any]:
    from kicad_ai.render.common import read_json

    if user_path:
        files = resolve_kicad_files(user_path)
        stem = (files["sch"] or files["pro"] or files["project_dir"]).stem
        path = project_render_dir(stem) / "render_report.json"
    else:
        path = get_workspace() / "renders" / "render_report.json"
    data = read_json(path)
    if not data:
        return {"success": False, "ok": False, "status": "FAIL", "reason": f"no render report at {path}"}
    data["success"] = True
    data["report"] = relpath(path)
    return data


def _paths_by_format(items: list[dict[str, Any]]) -> dict[str, str]:
    return {item["format"]: item["path"] for item in items if item.get("format") and item.get("path")}


def _slim(value: Any) -> Any:
    if isinstance(value, dict) and "artifacts" in value:
        return {
            "status": value.get("status"),
            "skipped": value.get("skipped"),
            "reason": value.get("reason"),
            "artifacts": value.get("artifacts"),
            "warnings": value.get("warnings"),
        }
    if isinstance(value, dict):
        return {key: _slim(item) for key, item in value.items()}
    return value


def format_banner(report: dict[str, Any]) -> str:
    sch = report.get("sections", {}).get("schematic") or report.get("schematic") or {}
    pcb = report.get("sections", {}).get("pcb") or {}
    three = report.get("sections", {}).get("pcb_3d") or {}

    def flag(item: dict[str, Any] | None, key: str) -> str:
        if not item:
            return "SKIPPED"
        if isinstance(item, dict) and key in item and isinstance(item[key], dict):
            return str(item[key].get("status") or "SKIPPED")
        return str(item.get("status") or "SKIPPED")

    lines = [
        "=====================================",
        " KiCad Project Rendering",
        "=====================================",
        "",
        "Schematic:",
        f"    SVG   {flag(sch if 'artifacts' in sch else {'status': 'PASS' if report.get('schematic', {}).get('svg') else 'SKIPPED'}, 'status')}",
        f"    PNG   {flag(sch if 'artifacts' in sch else {'status': 'PASS' if report.get('schematic', {}).get('png') else 'SKIPPED'}, 'status')}",
        f"    PDF   {flag(sch if 'artifacts' in sch else {'status': 'PASS' if report.get('schematic', {}).get('pdf') else 'SKIPPED'}, 'status')}",
        "",
        "PCB:",
        f"    Top       {_status(pcb, 'top')}",
        f"    Bottom    {_status(pcb, 'bottom')}",
        "",
        "PCB 3D:",
        f"    Top       {_status(three, 'top')}",
        f"    Isometric {_status(three, 'isometric')}",
        "",
        "Warnings:",
        f"    {len(report.get('warnings') or [])} missing 3D models / other",
        "",
        f"RESULT: {report.get('result') or report.get('status')}",
        "=====================================",
    ]
    if report.get("schematic"):
        for fmt, path in (report.get("schematic") or {}).items():
            lines.append(f"  schematic {fmt}: {path}")
    return "\n".join(lines)


def _status(section: Any, key: str) -> str:
    if not isinstance(section, dict):
        return "SKIPPED"
    item = section.get(key) if key in section else section
    if not isinstance(item, dict):
        return "SKIPPED"
    return str(item.get("status") or "SKIPPED")
