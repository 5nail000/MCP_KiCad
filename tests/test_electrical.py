from __future__ import annotations

from pathlib import Path

from kicad_ai.config import get_workspace, load_env
from kicad_ai.detect import require_kicad
from kicad_ai.kicad_cli import nets_from_schematic
from kicad_ai.logging_setup import setup_logging
from kicad_ai.paths import PathDenied
from kicad_ai.skidl_runtime import export_block_netlist
from kicad_ai.validate import validate_project


MCP_TEST = Path("projects/examples/mcp-test/mcp-test.kicad_sch")
OXY = Path("projects/oxy/oxy")


def setup_module() -> None:
    load_env()
    setup_logging()
    require_kicad()


def _mcp_test() -> Path:
    path = get_workspace() / MCP_TEST
    assert path.is_file(), f"missing example schematic {path}"
    return path


def test_kicad_erc_mcp_test_passes() -> None:
    report = validate_project(_mcp_test())
    erc = report["checks"]["erc"]
    assert erc["engine"] == "kicad-cli sch erc"
    assert erc["skipped"] is False
    assert erc["ok"] is True
    assert erc["status"] == "PASS"
    assert erc["violations"] == []


def test_mcp_test_has_example_pcb() -> None:
    pcb = _mcp_test().with_suffix(".kicad_pcb")
    assert pcb.is_file()
    text = pcb.read_text(encoding="utf-8", errors="replace")
    assert "(kicad_pcb" in text
    assert "Fuse:Fuse_0603_1608Metric" in text
    assert "Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT" in text
    assert "Resistor_SMD:R_0603_1608Metric" in text
    assert "LED_SMD:LED_0603_1608Metric" in text


def test_drc_skipped_when_project_has_no_pcb() -> None:
    oxy = get_workspace() / OXY
    assert oxy.is_dir()
    assert not (oxy / "oxy.kicad_pcb").is_file()
    report = validate_project(oxy)
    drc = report["checks"]["drc"]
    assert drc["skipped"] is True
    assert drc["status"] == "SKIPPED"
    assert "no .kicad_pcb" in drc["reason"]
    assert drc["status"] != "PASS"


def test_validate_mcp_test_passes_erc_and_drc() -> None:
    report = validate_project(_mcp_test())
    assert report["verdict"] == "PASS"
    assert report["ok"] is True
    assert "drc" not in report["skipped"]
    assert report["source_of_truth"].startswith("KiCad")
    assert report["checks"]["python"]["ok"] is True
    drc = report["checks"]["drc"]
    assert drc["skipped"] is False
    assert drc["status"] == "PASS"
    assert drc["violations"] == []
    assert report["checks"]["erc"]["status"] == "PASS"


def test_mcp_test_netlist_topology() -> None:
    nets = nets_from_schematic(_mcp_test())
    joined = {name: set(pins) for name, pins in nets.items()}
    fuse_to_reg = any("U1.1" in pins and any(p.startswith("F1.") for p in pins) for pins in joined.values())
    assert fuse_to_reg, joined
    five_volt = any("U1.3" in pins and any(p.startswith("R1.") for p in pins) for pins in joined.values())
    assert five_volt, joined
    gnd = any("U1.2" in pins and any(p.startswith("D1.") for p in pins) for pins in joined.values())
    assert gnd, joined


def test_skidl_netlist_writes_only_generated() -> None:
    dest = get_workspace() / "skidl_lab" / "generated" / "led_indicator.net"
    result = export_block_netlist("led_indicator", dest)
    assert Path(result["path"]).is_file()
    assert "skidl_lab" in result["path"].replace("\\", "/")
    assert "generated" in result["path"].replace("\\", "/")


def test_skidl_refuses_kicad_schematic_extension() -> None:
    dest = get_workspace() / "skidl_lab" / "generated" / "nope.kicad_sch"
    try:
        export_block_netlist("led_indicator", dest)
        raise AssertionError("expected PathDenied")
    except PathDenied:
        pass
