"""MCP stdio server wrapping kicad-sch-api + kicad-cli with a workspace whitelist."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from kicad_ai.backup import backup_project, list_backups, restore_backup
from kicad_ai.config import load_env
from kicad_ai.detect import require_kicad
from kicad_ai.libraries import search_symbols as lib_search
from kicad_ai.libraries import symbol_info
from kicad_ai.logging_setup import error_payload, get_logger, setup_logging
from kicad_ai.project import create_project as create_kicad_project
from kicad_ai.project import list_projects as list_kicad_projects
from kicad_ai import schematic as schops

mcp = FastMCP(
    "kicad-ai",
    instructions=(
        "Work only on real KiCad projects under this workspace. "
        "KiCad files under projects/ are the source of truth. "
        "Read an existing schematic before changing it. "
        "Never treat a visual wire crossing as an electrical connection. "
        "Use junctions, net labels, and power symbols correctly. "
        "Do not invent part numbers; search_symbols first. "
        "Do not delete components without confirm=true. "
        "SKiDL must not overwrite .kicad_sch. After edits: backup, inspect_connectivity, validate_project. "
        "Renders come from kicad-cli (SVG/PDF/3D PNG), never from AI image generation."
    ),
)


def _ok(payload: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"success": True}
    if payload:
        data.update(payload)
    data.update(extra)
    return data


def _fail(operation: str, error: BaseException, tool: str) -> dict[str, Any]:
    project = str(schops.SESSION.path) if schops.SESSION.path else None
    return error_payload(operation=operation, error=error, project=project, tool=tool)


@mcp.tool()
def list_projects() -> dict[str, Any]:
    """List KiCad projects under projects/examples and projects/user."""
    try:
        return _ok(projects=list_kicad_projects())
    except Exception as exc:  # noqa: BLE001
        return _fail("list_projects", exc, "list_projects")


@mcp.tool()
def create_project(name: str, location: str = "user", title: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Create a KiCad 10 project (.kicad_pro + .kicad_sch) under projects/user or projects/examples."""
    try:
        result = create_kicad_project(name, location=location, title=title, overwrite=overwrite)
        schops.load_schematic(result["schematic"])
        result["loaded"] = True
        return result
    except Exception as exc:  # noqa: BLE001
        return _fail("create_project", exc, "create_project")


@mcp.tool(name="backup_project")
def backup_project_tool(target: str) -> dict[str, Any]:
    """Copy a project into backups/<name>/<timestamp>/ and prune old copies."""
    try:
        dest = backup_project(target)
        return _ok(backup_dir=str(dest))
    except Exception as exc:  # noqa: BLE001
        return _fail("backup_project", exc, "backup_project")


@mcp.tool(name="restore_backup")
def restore_backup_tool(project_dir: str, backup_dir: str) -> dict[str, Any]:
    """Restore a previously created backup over a project directory."""
    try:
        dest = restore_backup(project_dir, backup_dir)
        return _ok(project_dir=str(dest))
    except Exception as exc:  # noqa: BLE001
        return _fail("restore_backup", exc, "restore_backup")


@mcp.tool()
def list_project_backups(project_name: str) -> dict[str, Any]:
    """List timestamped backups for a project folder name."""
    try:
        items = [str(path) for path in list_backups(project_name)]
        return _ok(backups=items)
    except Exception as exc:  # noqa: BLE001
        return _fail("list_project_backups", exc, "list_project_backups")


@mcp.tool()
def load_schematic(file_path: str) -> dict[str, Any]:
    """Load an existing .kicad_sch file from the workspace."""
    try:
        return schops.load_schematic(file_path)
    except Exception as extra:  # noqa: BLE001
        return _fail("load_schematic", extra, "load_schematic")


@mcp.tool()
def save_schematic(file_path: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Save the loaded schematic. Existing files are backed up first. dry_run previews without writing."""
    try:
        return schops.save_schematic(file_path, dry_run=dry_run)
    except Exception as extra:
        return _fail("save_schematic", extra, "save_schematic")


@mcp.tool()
def get_schematic_info() -> dict[str, Any]:
    """Return metadata and component list for the loaded schematic."""
    try:
        return schops.get_schematic_info()
    except Exception as extra:
        return _fail("get_schematic_info", extra, "get_schematic_info")


@mcp.tool()
def search_symbols(query: str, library: str | None = None, limit: int = 40) -> dict[str, Any]:
    """Search official KiCad symbol libraries. Do not invent a part number if nothing matches."""
    try:
        hits = lib_search(query, library=library, limit=limit)
        return _ok(count=len(hits), symbols=hits)
    except Exception as extra:
        return _fail("search_symbols", extra, "search_symbols")


@mcp.tool()
def get_symbol_info(lib_id: str) -> dict[str, Any]:
    """Exact symbol lookup (pins, datasheet field, description) from KiCad libraries."""
    try:
        return _ok(symbol=symbol_info(lib_id))
    except Exception as extra:
        return _fail("get_symbol_info", extra, "get_symbol_info")


@mcp.tool()
def add_component(
    lib_id: str,
    reference: str | None = None,
    value: str = "",
    x: float | None = None,
    y: float | None = None,
    rotation: float = 0.0,
    footprint: str | None = None,
) -> dict[str, Any]:
    """Add a real KiCad library symbol to the loaded schematic. Positions are millimetres on the 1.27mm grid."""
    try:
        position = {"x": x, "y": y} if x is not None and y is not None else None
        return schops.add_component(
            lib_id,
            reference=reference,
            value=value,
            position=position,
            rotation=rotation,
            footprint=footprint,
        )
    except Exception as extra:
        return _fail("add_component", extra, "add_component")


@mcp.tool()
def list_components() -> dict[str, Any]:
    """List components in the loaded schematic."""
    try:
        return schops.list_components()
    except Exception as extra:
        return _fail("list_components", extra, "list_components")


@mcp.tool()
def update_component(
    reference: str,
    value: str | None = None,
    x: float | None = None,
    y: float | None = None,
    rotation: float | None = None,
    footprint: str | None = None,
) -> dict[str, Any]:
    """Update value, position, rotation, or footprint. Does not change the reference designator."""
    try:
        position = {"x": x, "y": y} if x is not None and y is not None else None
        return schops.update_component(
            reference,
            value=value,
            position=position,
            rotation=rotation,
            footprint=footprint,
        )
    except Exception as extra:
        return _fail("update_component", extra, "update_component")


@mcp.tool()
def remove_component(reference: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a component. Requires confirm=true. Never delete silently."""
    try:
        return schops.remove_component(reference, confirm=confirm)
    except Exception as extra:
        return _fail("remove_component", extra, "remove_component")


@mcp.tool()
def get_component_pins(reference: str) -> dict[str, Any]:
    """Return pin numbers and schematic coordinates for a component."""
    try:
        return schops.get_component_pins(reference)
    except Exception as extra:
        return _fail("get_component_pins", extra, "get_component_pins")


@mcp.tool()
def add_wire(x1: float, y1: float, x2: float, y2: float) -> dict[str, Any]:
    """Draw a schematic wire between two millimetre coordinates. Prefer orthogonal segments."""
    try:
        return schops.add_wire((x1, y1), (x2, y2))
    except Exception as extra:
        return _fail("add_wire", extra, "add_wire")


@mcp.tool()
def connect_pins(ref_a: str, pin_a: str, ref_b: str, pin_b: str) -> dict[str, Any]:
    """Electrically connect two component pins with a wire (not a visual crossing)."""
    try:
        return schops.connect_pins(ref_a, pin_a, ref_b, pin_b)
    except Exception as extra:
        return _fail("connect_pins", extra, "connect_pins")


@mcp.tool()
def add_label(text: str, x: float, y: float) -> dict[str, Any]:
    """Place a local net label. Same-name labels are electrically connected."""
    try:
        return schops.add_label(text, (x, y))
    except Exception as extra:
        return _fail("add_label", extra, "add_label")


@mcp.tool()
def add_power_symbol(lib_id: str, x: float, y: float, reference: str | None = None) -> dict[str, Any]:
    """Place a power symbol such as power:+12V, power:+5V, power:GND, power:PWR_FLAG."""
    try:
        return schops.add_power_symbol(lib_id, reference=reference, position=(x, y))
    except Exception as extra:
        return _fail("add_power_symbol", extra, "add_power_symbol")


@mcp.tool()
def add_junction(x: float, y: float) -> dict[str, Any]:
    """Place a junction. Required at T-connections; crossing wires without a junction are NOT connected."""
    try:
        return schops.add_junction((x, y))
    except Exception as extra:
        return _fail("add_junction", extra, "add_junction")


@mcp.tool()
def inspect_connectivity() -> dict[str, Any]:
    """Trace nets through wires, labels, junctions, and power symbols. Wire crossings are not connections."""
    try:
        return schops.inspect_connectivity()
    except Exception as extra:
        return _fail("inspect_connectivity", extra, "inspect_connectivity")


@mcp.tool()
def are_pins_connected(ref_a: str, pin_a: str, ref_b: str, pin_b: str) -> dict[str, Any]:
    """Return whether two pins are on the same electrical net."""
    try:
        return schops.are_pins_connected(ref_a, pin_a, ref_b, pin_b)
    except Exception as extra:
        return _fail("are_pins_connected", extra, "are_pins_connected")


@mcp.tool()
def run_erc(file_path: str | None = None) -> dict[str, Any]:
    """Run KiCad ERC via kicad-cli sch erc on a saved .kicad_sch. Save first if using the loaded schematic."""
    try:
        return schops.run_erc(file_path)
    except Exception as extra:
        return _fail("run_erc", extra, "run_erc")


@mcp.tool()
def run_drc(file_path: str | None = None) -> dict[str, Any]:
    """Run KiCad DRC via kicad-cli pcb drc. If there is no .kicad_pcb, returns SKIPPED (not a fake PASS)."""
    try:
        return schops.run_drc(file_path)
    except Exception as extra:
        return _fail("run_drc", extra, "run_drc")


@mcp.tool()
def validate_project(path: str, run_skidl: bool = False, skidl_block: str | None = None) -> dict[str, Any]:
    """KiCad ERC + DRC (skipped without PCB) + Python sanity. Optional SKiDL ERC on a lab block — never writes the KiCad schematic."""
    try:
        from kicad_ai.validate import validate_project as run_validate

        return run_validate(path, run_skidl=run_skidl, skidl_block=skidl_block)
    except Exception as extra:
        return _fail("validate_project", extra, "validate_project")


@mcp.tool()
def list_skidl_blocks() -> dict[str, Any]:
    """List reusable SKiDL blocks under skidl_lab/. These are not KiCad project schematics."""
    try:
        from kicad_ai.skidl_runtime import list_blocks

        return _ok(blocks=list_blocks(), source_of_truth="projects/ KiCad files, not SKiDL")
    except Exception as extra:
        return _fail("list_skidl_blocks", extra, "list_skidl_blocks")


@mcp.tool()
def run_skidl_erc(block: str) -> dict[str, Any]:
    """Run SKiDL ERC on a lab block. Does not modify .kicad_sch under projects/."""
    try:
        from kicad_ai.skidl_runtime import run_block_erc

        return run_block_erc(block)
    except Exception as extra:
        return _fail("run_skidl_erc", extra, "run_skidl_erc")


@mcp.tool()
def export_skidl_netlist(block: str, output: str | None = None) -> dict[str, Any]:
    """Write a SKiDL netlist only under skidl_lab/generated/. Refuses projects/ and .kicad_sch."""
    try:
        from kicad_ai.skidl_runtime import export_block_netlist

        return export_block_netlist(block, output)
    except Exception as extra:
        return _fail("export_skidl_netlist", extra, "export_skidl_netlist")


@mcp.tool()
def export_bom(output: str | None = None) -> dict[str, Any]:
    """Export a BOM CSV via kicad-cli sch export bom."""
    try:
        return schops.export_bom(output)
    except Exception as extra:
        return _fail("export_bom", extra, "export_bom")


@mcp.tool()
def export_netlist(output: str | None = None) -> dict[str, Any]:
    """Export a KiCad netlist via kicad-cli sch export netlist."""
    try:
        return schops.export_netlist(output)
    except Exception as extra:
        return _fail("export_netlist", extra, "export_netlist")


@mcp.tool()
def render_schematic(
    path: str,
    view: str = "full",
    theme: str | None = None,
    quality: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Export a real KiCad schematic render (SVG/PNG/PDF) via kicad-cli. Not an AI image."""
    try:
        from kicad_ai.render.schematic import render_schematic as do_render

        return do_render(path, view=view, theme=theme, quality=quality, force=force)
    except Exception as extra:
        return _fail("render_schematic", extra, "render_schematic")


@mcp.tool()
def render_pcb(path: str, side: str = "top", force: bool = False) -> dict[str, Any]:
    """2D PCB plot via kicad-cli pcb export svg. No .kicad_pcb → SKIPPED, not a fake image."""
    try:
        from kicad_ai.render.pcb import render_pcb as do_render

        return do_render(path, side=side, force=force)
    except Exception as extra:
        return _fail("render_pcb", extra, "render_pcb")


@mcp.tool()
def render_pcb_3d(path: str, camera: str = "isometric", force: bool = False) -> dict[str, Any]:
    """KiCad 3D viewer PNG (`kicad-cli pcb render`). Missing 3D models are warnings. No PCB → SKIPPED."""
    try:
        from kicad_ai.render.pcb import render_pcb_3d as do_render

        return do_render(path, camera=camera, force=force)
    except Exception as extra:
        return _fail("render_pcb_3d", extra, "render_pcb_3d")


@mcp.tool()
def render_project(path: str, force: bool = False, theme: str | None = None, quality: str | None = None) -> dict[str, Any]:
    """Render schematic (and PCB/3D if the board exists). Writes renders/<project>/ and render_report.json."""
    try:
        from kicad_ai.render.project_render import render_project as do_render

        return do_render(path, theme=theme, quality=quality, force=force)
    except Exception as extra:
        return _fail("render_project", extra, "render_project")


@mcp.tool()
def get_render_report(path: str | None = None) -> dict[str, Any]:
    """Return the last render_report.json (relative artifact paths)."""
    try:
        from kicad_ai.render.project_render import get_render_report as load_report

        return load_report(path)
    except Exception as extra:
        return _fail("get_render_report", extra, "get_render_report")


def main() -> None:
    load_env()
    setup_logging()
    require_kicad()
    logger = get_logger()
    logger.info("Starting kicad-ai MCP server (stdio)")
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
