from __future__ import annotations

from kicad_ai.skidl_runtime import erc_circuit, export_block_netlist, list_blocks, run_block_erc
from kicad_ai.paths import PathDenied
from kicad_ai.config import get_workspace
from skidl_lab.circuits.mcp_test_equivalent import build as build_equivalent


def test_skidl_blocks_are_registered() -> None:
    names = list_blocks()
    assert "led_indicator" in names
    assert "rail_12v_5v" in names


def test_led_indicator_skidl_erc_passes() -> None:
    result = run_block_erc("led_indicator")
    assert result["engine"] == "skidl ERC"
    assert result["ok"] is True
    assert result["errors"] == 0
    assert result["warnings"] == 0
    assert result["writes_kicad_schematic"] is False


def test_rail_12v_5v_skidl_erc_passes() -> None:
    result = run_block_erc("rail_12v_5v")
    assert result["ok"] is True
    assert result["errors"] == 0
    refs = set(result["parts"])
    assert {"F1", "U1", "R1", "D1"} <= refs or len(refs) >= 4


def test_mcp_test_equivalent_is_not_a_kicad_file() -> None:
    circuit = build_equivalent()
    result = erc_circuit(circuit)
    assert result["ok"] is True
    assert result["writes_kicad_schematic"] is False


def test_skidl_erc_detects_unconnected_pins() -> None:
    from skidl import Circuit, Part

    circuit = Circuit()
    circuit.no_files = True
    Part("Device", "R", value="1k", circuit=circuit)
    result = erc_circuit(circuit)
    assert result["ok"] is False
    assert result["warnings"] > 0 or result["errors"] > 0


def test_skidl_netlist_cannot_write_projects() -> None:
    dest = get_workspace() / "projects" / "user" / "forbidden.net"
    try:
        export_block_netlist("led_indicator", dest)
        raise AssertionError("expected PathDenied")
    except PathDenied:
        pass
