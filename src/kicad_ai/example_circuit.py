"""Build the example 12V → fuse → R-78E 5V → LED circuit from official KiCad symbols."""

from __future__ import annotations

from typing import Any

from kicad_ai.config import get_workspace
from kicad_ai.logging_setup import get_logger
from kicad_ai.project import create_project
from kicad_ai import schematic as schops

# Real KiCad 10 library identifiers (verified in Device/power/Converter_DCDC).
PWR_12V = "power:+12V"
PWR_5V = "power:+5V"
PWR_GND = "power:GND"
PWR_FLAG = "power:PWR_FLAG"
FUSE = "Device:Fuse"
REG = "Converter_DCDC:R-78E5.0-0.5"
LED = "Device:LED"
RES = "Device:R"
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_FUSE = "Fuse:Fuse_0603_1608Metric"
FP_REG = "Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT"


def create_mcp_test_project(
    *,
    name: str = "mcp-test",
    location: str = "examples",
    overwrite: bool = True,
) -> dict[str, Any]:
    """Create a 12V-to-5V indicator KiCad project from official symbols."""
    logger = get_logger()
    created = create_project(name, location=location, title="MCP Test 12V to 5V", overwrite=overwrite)
    schops.load_schematic(created["schematic"])

    # One horizontal power row at y=63.50 so fuse pins do not sit on a wire to the other fuse pin.
    schops.add_power_symbol(PWR_FLAG, reference="#FLG01", position=(38.10, 63.50))
    schops.add_power_symbol(PWR_12V, reference="#PWR01", position=(50.80, 63.50))
    schops.add_component(FUSE, reference="F1", value="2A", position=(88.90, 63.50), rotation=90, footprint=FP_FUSE)
    schops.add_component(REG, reference="U1", value="R-78E5.0-0.5", position=(139.70, 63.50), footprint=FP_REG)
    schops.add_power_symbol(PWR_FLAG, reference="#FLG02", position=(127.00, 38.10))
    schops.add_power_symbol(PWR_5V, reference="#PWR02", position=(190.50, 63.50))
    schops.add_component(RES, reference="R1", value="1k", position=(190.50, 101.60), footprint=FP_R)
    schops.add_component(LED, reference="D1", value="LED", position=(190.50, 127.00), footprint=FP_LED)
    schops.add_power_symbol(PWR_GND, reference="#PWR03", position=(139.70, 101.60))
    schops.add_power_symbol(PWR_GND, reference="#PWR04", position=(190.50, 152.40))
    schops.add_power_symbol(PWR_FLAG, reference="#FLG03", position=(114.30, 101.60))

    connections = [
        ("#FLG01", "1", "#PWR01", "1"),
        ("#PWR01", "1", "F1", "2"),
        ("F1", "1", "U1", "1"),
        ("#FLG02", "1", "U1", "1"),
        ("U1", "3", "#PWR02", "1"),
        ("#PWR02", "1", "R1", "1"),
        ("R1", "2", "D1", "2"),
        ("D1", "1", "#PWR04", "1"),
        ("U1", "2", "#PWR03", "1"),
        ("#FLG03", "1", "#PWR03", "1"),
    ]
    wired: list[dict[str, Any]] = []
    for ref_a, pin_a, ref_b, pin_b in connections:
        wired.append(schops.connect_pins(ref_a, pin_a, ref_b, pin_b))

    saved = schops.save_schematic(created["schematic"])
    connectivity = schops.inspect_connectivity()
    logger.info("Example project ready: %s", created["project"])
    notes = get_workspace() / "components" / "R-78E5.0-0.5" / "notes.md"
    return {
        "success": True,
        "project": created,
        "saved": saved,
        "connections": wired,
        "connectivity": connectivity,
        "datasheet_notes": str(notes) if notes.is_file() else None,
        "symbols": {
            "fuse": FUSE,
            "regulator": REG,
            "led": LED,
            "resistor": RES,
        },
    }
