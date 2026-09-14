"""Workspace render settings. Presentation only — does not change KiCad source files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kicad_ai.config import get_workspace
from kicad_ai.logging_setup import get_logger

DEFAULT_CONFIG_NAME = "render.yaml"


@dataclass(frozen=True)
class SchematicView:
    name: str
    description: str = ""
    references: tuple[str, ...] = ()
    padding_mm: float | None = None


@dataclass(frozen=True)
class RenderConfig:
    dpi: int = 300
    preview_dpi: int = 150
    docs_dpi: int = 300
    large_dpi: int = 600
    margin_mm: float = 15.0
    theme: str = "light"
    backend: str = "kicad_cli"
    pcb_background: str = "transparent"
    pcb_width: int = 1600
    pcb_height: int = 900
    pcb_quality: str = "high"
    render_after_validation: bool = False
    views: tuple[SchematicView, ...] = ()


def default_config() -> RenderConfig:
    return RenderConfig(
        views=(
            SchematicView("power", "Power input, fuse and DC-DC", ("F1", "U1")),
            SchematicView("controller", "MCU / controller", ("U2", "U3", "ESP32")),
            SchematicView("sensors", "Sensors", ("J_SENS", "U_SENS")),
            SchematicView("actuators", "Valves, pump and servos", ("K1", "M1", "Q1")),
            SchematicView("communication", "Communication", ("U_USB", "J_UART")),
            SchematicView("indicator", "5V LED indicator (mcp-test)", ("R1", "D1")),
        )
    )


def load_render_config(workspace: Path | None = None) -> RenderConfig:
    root = workspace or get_workspace()
    path = root / DEFAULT_CONFIG_NAME
    base = default_config()
    if not path.is_file():
        return base
    try:
        import yaml
    except ImportError:
        get_logger().warning("PyYAML is missing; using default render config")
        return base
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _from_mapping(data, base)


def _from_mapping(data: dict[str, Any], base: RenderConfig) -> RenderConfig:
    block = data.get("render") or {}
    pcb = data.get("pcb_render") or {}
    auto = data.get("automation") or block.get("automation") or {}
    views_raw = data.get("schematic_views") or []
    views: list[SchematicView] = []
    for item in views_raw:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        refs = item.get("references") or []
        views.append(
            SchematicView(
                name=str(item["name"]),
                description=str(item.get("description") or ""),
                references=tuple(str(r) for r in refs),
                padding_mm=float(item["padding_mm"]) if item.get("padding_mm") is not None else None,
            )
        )
    bg = str(pcb.get("background") or base.pcb_background).lower()
    if bg not in {"transparent", "white", "opaque"}:
        bg = "transparent"
    theme = str(block.get("theme") or base.theme).lower()
    if theme not in {"light", "dark"}:
        theme = "light"
    return RenderConfig(
        dpi=int(block.get("dpi") or base.dpi),
        preview_dpi=int(block.get("preview_dpi") or base.preview_dpi),
        docs_dpi=int(block.get("docs_dpi") or block.get("dpi") or base.docs_dpi),
        large_dpi=int(block.get("large_dpi") or base.large_dpi),
        margin_mm=float(block.get("margin") or base.margin_mm),
        theme=theme,
        backend=str(block.get("backend") or base.backend),
        pcb_background=bg,
        pcb_width=int(pcb.get("width") or base.pcb_width),
        pcb_height=int(pcb.get("height") or base.pcb_height),
        pcb_quality=str(pcb.get("quality") or base.pcb_quality),
        render_after_validation=bool(auto.get("render_after_validation", base.render_after_validation)),
        views=tuple(views) if views else base.views,
    )


def resolve_dpi(config: RenderConfig, quality: str | None) -> int:
    key = (quality or "docs").lower()
    if key in {"preview", "150"}:
        return config.preview_dpi
    if key in {"large", "600"}:
        return config.large_dpi
    if key in {"docs", "documentation", "300"}:
        return config.docs_dpi
    try:
        return max(72, int(key))
    except ValueError:
        return config.dpi
