"""Schematic operations on real .kicad_sch files via kicad-sch-api."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import kicad_sch_api as ksa

from kicad_ai.backup import backup_project
from kicad_ai.detect import require_kicad
from kicad_ai.kicad_cli import export_bom as cli_export_bom
from kicad_ai.kicad_cli import export_netlist as cli_export_netlist
from kicad_ai.kicad_cli import run_drc as cli_run_drc
from kicad_ai.kicad_cli import run_erc as cli_run_erc
from kicad_ai.kicad_cli import skipped_drc
from kicad_ai.kicad_cli import upgrade_schematic
from kicad_ai.libraries import symbol_info
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed, find_lock_files, project_root_for


def _point(value: Any) -> dict[str, float] | None:
    if value is None:
        return None
    if isinstance(value, dict) and "x" in value and "y" in value:
        return {"x": float(value["x"]), "y": float(value["y"])}
    x = getattr(value, "x", None)
    y = getattr(value, "y", None)
    if x is not None and y is not None:
        return {"x": float(x), "y": float(y)}
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return {"x": float(value[0]), "y": float(value[1])}
    return None


def _as_xy(position: Any) -> tuple[float, float]:
    if isinstance(position, dict):
        return float(position["x"]), float(position["y"])
    if hasattr(position, "x"):
        return float(position.x), float(position.y)
    return float(position[0]), float(position[1])


def serialize_component(component: Any) -> dict[str, Any]:
    return {
        "reference": getattr(component, "reference", None),
        "lib_id": getattr(component, "lib_id", None),
        "value": getattr(component, "value", None),
        "footprint": getattr(component, "footprint", None),
        "position": _point(getattr(component, "position", None)),
        "rotation": getattr(component, "rotation", 0),
    }


@dataclass
class SchematicSession:
    schematic: Any = None
    path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def require(self) -> Any:
        if self.schematic is None:
            raise RuntimeError("No schematic loaded. Call load_schematic or create_project first.")
        return self.schematic


SESSION = SchematicSession()


def current_session() -> SchematicSession:
    return SESSION


def load_schematic(file_path: str) -> dict[str, Any]:
    require_kicad()
    path = assert_allowed(file_path, write=False)
    if not path.is_file():
        raise FileNotFoundError(f"Schematic not found: {path}")
    if path.suffix != ".kicad_sch":
        raise ValueError("File must have .kicad_sch extension")
    locks = find_lock_files(path.parent)
    sch = ksa.load_schematic(str(path))
    SESSION.schematic = sch
    SESSION.path = path
    SESSION.warnings = [f"KiCad lock file present: {lock}" for lock in locks]
    logger = get_logger()
    logger.info("Loaded schematic %s (%s components)", path, len(list(sch.components.all())))
    return get_schematic_info()


def save_schematic(file_path: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    sch = SESSION.require()
    target = assert_allowed(file_path or SESSION.path, write=True)
    if target.suffix != ".kicad_sch":
        raise ValueError("File must have .kicad_sch extension")
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "would_save": str(target),
            "info": get_schematic_info(),
        }
    if target.is_file():
        backup_project(target)
    locks = find_lock_files(target.parent)
    if locks:
        get_logger().warning("Writing schematic while lock files exist: %s", locks)
    target.parent.mkdir(parents=True, exist_ok=True)
    sch.save(str(target))
    try:
        upgrade_schematic(target)
    except Exception as exc:  # noqa: BLE001 — upgrade is best-effort compatibility with KiCad 10
        get_logger().warning("kicad-cli sch upgrade skipped/failed: %s", exc)
    SESSION.path = target
    SESSION.schematic = ksa.load_schematic(str(target))
    return {
        "success": True,
        "file_path": str(target),
        "backup": True if target.is_file() else False,
        "locks": [str(p) for p in locks],
        "info": get_schematic_info(),
    }


def get_schematic_info() -> dict[str, Any]:
    sch = SESSION.require()
    components = [serialize_component(c) for c in sch.components.all()]
    stats = sch.get_statistics() if hasattr(sch, "get_statistics") else {}
    title = getattr(getattr(sch, "title_block", None), "title", None)
    if isinstance(sch.title_block, dict):
        title = sch.title_block.get("title", title)
    return {
        "success": True,
        "file_path": str(SESSION.path) if SESSION.path else None,
        "project_name": title or getattr(sch, "name", None),
        "uuid": str(sch.uuid),
        "component_count": len(components),
        "components": components,
        "statistics": stats,
        "warnings": list(SESSION.warnings),
        "locks": [str(p) for p in find_lock_files(SESSION.path.parent)] if SESSION.path else [],
    }


def add_component(
    lib_id: str,
    *,
    reference: str | None = None,
    value: str = "",
    position: dict[str, float] | list[float] | tuple[float, float] | None = None,
    rotation: float = 0.0,
    footprint: str | None = None,
) -> dict[str, Any]:
    sch = SESSION.require()
    info = symbol_info(lib_id)
    xy = _as_xy(position) if position is not None else None
    component = sch.components.add(
        lib_id,
        reference=reference,
        value=value or info.get("name") or "",
        position=xy,
        footprint=footprint,
        rotation=rotation,
    )
    get_logger().info("Added component %s (%s)", getattr(component, "reference", reference), lib_id)
    return {"success": True, "component": serialize_component(component), "symbol": info}


def list_components() -> dict[str, Any]:
    sch = SESSION.require()
    items = [serialize_component(c) for c in sch.components.all()]
    return {"success": True, "count": len(items), "components": items}


def update_component(
    reference: str,
    *,
    value: str | None = None,
    position: dict[str, float] | list[float] | tuple[float, float] | None = None,
    rotation: float | None = None,
    footprint: str | None = None,
) -> dict[str, Any]:
    sch = SESSION.require()
    component = sch.components.get(reference)
    if component is None:
        raise KeyError(f"Component not found: {reference}")
    if value is not None:
        component.value = value
    if footprint is not None:
        component.footprint = footprint
    if position is not None:
        xy = _as_xy(position)
        if hasattr(component, "move"):
            try:
                component.move(xy)
            except TypeError:
                component.position = xy
        else:
            component.position = xy
    if rotation is not None and hasattr(component, "rotate"):
        try:
            component.rotate(rotation)
        except TypeError:
            component.rotation = rotation
    elif rotation is not None:
        component.rotation = rotation
    return {"success": True, "component": serialize_component(component)}


def remove_component(reference: str, *, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        raise PermissionError("Refusing to delete a component without confirm=true")
    sch = SESSION.require()
    before = serialize_component(sch.components.get(reference)) if sch.components.get(reference) else None
    if before is None:
        raise KeyError(f"Component not found: {reference}")
    sch.components.remove(reference)
    get_logger().info("Removed component %s", reference)
    return {"success": True, "removed": before}


def get_component_pins(reference: str) -> dict[str, Any]:
    sch = SESSION.require()
    pins = []
    for item in sch.list_component_pins(reference):
        if isinstance(item, tuple) and len(item) == 2:
            number, pos = item
            pins.append({"number": str(number), "position": _point(pos)})
        else:
            pins.append({"raw": str(item)})
    component = sch.components.get(reference)
    extra = []
    if component is not None and hasattr(component, "list_pins"):
        try:
            extra = component.list_pins()
        except Exception:  # noqa: BLE001
            extra = []
    return {"success": True, "reference": reference, "pins": pins, "details": extra}


def add_wire(
    start: dict[str, float] | list[float] | tuple[float, float],
    end: dict[str, float] | list[float] | tuple[float, float],
) -> dict[str, Any]:
    sch = SESSION.require()
    wire_id = sch.add_wire(_as_xy(start), _as_xy(end))
    return {"success": True, "wire_uuid": wire_id}


def _manhattan_segments(
    start: tuple[float, float], end: tuple[float, float]
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    x1, y1 = start
    x2, y2 = end
    if abs(x1 - x2) < 0.02 or abs(y1 - y2) < 0.02:
        return [(start, end)]
    corner = (x2, y1)
    return [(start, corner), (corner, end)]


def connect_pins(ref_a: str, pin_a: str, ref_b: str, pin_b: str) -> dict[str, Any]:
    sch = SESSION.require()
    pins_a = {item["number"]: item["position"] for item in get_component_pins(ref_a)["pins"] if item.get("position")}
    pins_b = {item["number"]: item["position"] for item in get_component_pins(ref_b)["pins"] if item.get("position")}
    if str(pin_a) not in pins_a or str(pin_b) not in pins_b:
        raise KeyError(f"Missing pin coordinates for {ref_a}.{pin_a} or {ref_b}.{pin_b}")
    start = (pins_a[str(pin_a)]["x"], pins_a[str(pin_a)]["y"])
    end = (pins_b[str(pin_b)]["x"], pins_b[str(pin_b)]["y"])
    wire_ids: list[str] = []
    segments = _manhattan_segments(start, end)
    for seg_start, seg_end in segments:
        wire_ids.append(sch.add_wire(seg_start, seg_end))
    if len(segments) > 1:
        corner = segments[0][1]
        sch.junctions.add(corner)
    return {
        "success": True,
        "wire_uuid": wire_ids,
        "from": f"{ref_a}.{pin_a}",
        "to": f"{ref_b}.{pin_b}",
        "note": "Electrical connection is pin-to-pin or via labels/power symbols, not visual wire crossing.",
    }


def add_label(text: str, position: dict[str, float] | list[float] | tuple[float, float]) -> dict[str, Any]:
    sch = SESSION.require()
    label_id = sch.add_label(text, _as_xy(position))
    return {"success": True, "label_uuid": label_id, "text": text}


def add_power_symbol(
    lib_id: str,
    *,
    reference: str | None = None,
    position: dict[str, float] | list[float] | tuple[float, float],
) -> dict[str, Any]:
    if not lib_id.startswith("power:"):
        raise ValueError("Power symbols must use lib_id like power:+12V, power:+5V, power:GND")
    value = lib_id.split(":", 1)[1]
    return add_component(lib_id, reference=reference, value=value, position=position)


def add_junction(position: dict[str, float] | list[float] | tuple[float, float]) -> dict[str, Any]:
    sch = SESSION.require()
    junction_id = sch.junctions.add(_as_xy(position))
    return {"success": True, "junction_uuid": junction_id}


def inspect_connectivity() -> dict[str, Any]:
    sch = SESSION.require()
    components = list(sch.components.all())
    pin_reports: list[dict[str, Any]] = []
    dangling: list[str] = []
    nets: dict[str, list[str]] = {}
    analyzer = "kicad-cli-netlist"
    if SESSION.path is not None:
        from kicad_ai.kicad_cli import nets_from_schematic

        try:
            nets = nets_from_schematic(SESSION.path)
        except Exception as exc:  # noqa: BLE001
            get_logger().warning("kicad-cli netlist connectivity failed: %s", exc)
            analyzer = "pin-list-only"
    pin_to_net = {pin: name for name, pins in nets.items() for pin in pins}
    for component in components:
        ref = component.reference
        for number, pos in sch.list_component_pins(ref):
            pin_id = f"{ref}.{number}"
            net_name = pin_to_net.get(pin_id)
            if net_name is None and not str(ref).startswith("#"):
                dangling.append(pin_id)
            pin_reports.append({"pin": pin_id, "position": _point(pos), "net": net_name})
    labels = []
    if hasattr(sch, "labels"):
        try:
            labels = [getattr(lab, "text", str(lab)) for lab in sch.labels.all()]
        except Exception:  # noqa: BLE001
            labels = []
    return {
        "success": True,
        "file_path": str(SESSION.path) if SESSION.path else None,
        "analyzer": analyzer,
        "component_count": len(components),
        "pins": pin_reports,
        "dangling_pins": dangling,
        "nets": nets,
        "labels": labels,
        "statistics": sch.get_statistics() if hasattr(sch, "get_statistics") else {},
        "rules": {
            "wire_crossing_is_not_a_connection": True,
            "junction_required_for_tee": True,
            "net_label_connects_by_name": True,
            "power_symbol_is_global_net": True,
        },
        "note": (
            "kicad-sch-api get_net_for_pin currently raises TypeError (unhashable Net) "
            "on this KiCad 10 schematic. Connectivity is taken from kicad-cli netlist."
        ),
    }


def are_pins_connected(ref_a: str, pin_a: str, ref_b: str, pin_b: str) -> dict[str, Any]:
    info = inspect_connectivity()
    pin_to_net = {pin: name for name, pins in info.get("nets", {}).items() for pin in pins}
    left = pin_to_net.get(f"{ref_a}.{pin_a}")
    right = pin_to_net.get(f"{ref_b}.{pin_b}")
    connected = left is not None and left == right
    return {
        "success": True,
        "connected": connected,
        "from": f"{ref_a}.{pin_a}",
        "to": f"{ref_b}.{pin_b}",
        "net": left if connected else None,
    }


def run_erc(file_path: str | None = None) -> dict[str, Any]:
    path = assert_allowed(file_path, write=False) if file_path else SESSION.path
    if path is None:
        raise RuntimeError("Save the schematic before running kicad-cli ERC")
    return cli_run_erc(path)


def run_drc(file_path: str | None = None) -> dict[str, Any]:
    if file_path:
        pcb = assert_allowed(file_path, write=False)
    elif SESSION.path is not None:
        pcb = SESSION.path.with_suffix(".kicad_pcb")
    else:
        raise RuntimeError("Pass a .kicad_pcb path or load a schematic first")
    if pcb.suffix != ".kicad_pcb":
        pcb = pcb.with_suffix(".kicad_pcb")
    if not pcb.is_file():
        return skipped_drc(reason="no .kicad_pcb next to the schematic", pcb=pcb)
    return cli_run_drc(pcb)


def export_bom(output: str | None = None) -> dict[str, Any]:
    if SESSION.path is None:
        raise RuntimeError("Save the schematic before exporting BOM")
    out = assert_allowed(output, write=True) if output else None
    return cli_export_bom(SESSION.path, output=out)


def export_netlist(output: str | None = None) -> dict[str, Any]:
    if SESSION.path is None:
        raise RuntimeError("Save the schematic before exporting netlist")
    out = assert_allowed(output, write=True) if output else None
    return cli_export_netlist(SESSION.path, output=out)


def project_dir_of_current() -> Path | None:
    if SESSION.path is None:
        return None
    return project_root_for(SESSION.path)
