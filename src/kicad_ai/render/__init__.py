"""KiCad-derived rendering. Source of truth remains .kicad_sch / .kicad_pcb."""

from __future__ import annotations

from kicad_ai.render.engine import AIRenderer, BlenderRenderer, KiCadRenderer, Renderer
from kicad_ai.render.project_render import format_banner, get_render_report, render_project
from kicad_ai.render.pcb import render_pcb, render_pcb_3d
from kicad_ai.render.schematic import list_schematic_views, render_schematic

__all__ = [
    "AIRenderer",
    "BlenderRenderer",
    "KiCadRenderer",
    "Renderer",
    "format_banner",
    "get_render_report",
    "list_schematic_views",
    "render_pcb",
    "render_pcb_3d",
    "render_project",
    "render_schematic",
]
