from __future__ import annotations

from pathlib import Path

from kicad_ai.config import load_env
from kicad_ai.detect import require_kicad
from kicad_ai.example_circuit import create_mcp_test_project
from kicad_ai.logging_setup import setup_logging
from kicad_ai.paths import PathDenied, assert_allowed
from kicad_ai import schematic as schops


def setup_module() -> None:
    load_env()
    setup_logging()
    require_kicad()


def test_whitelist_blocks_outside_workspace() -> None:
    try:
        assert_allowed(Path(r"C:\Windows\System32\drivers\etc\hosts"), write=True)
        raise AssertionError("expected PathDenied")
    except PathDenied:
        pass


def test_smoke_create_connect_save_reload_validate() -> None:
    result = create_mcp_test_project(name="smoke-tmp", location="user", overwrite=True)
    assert result["success"]
    schematic = Path(result["project"]["schematic"])
    project = Path(result["project"]["project"])
    assert schematic.is_file()
    assert project.is_file()
    assert "kicad_sch" in schematic.read_text(encoding="utf-8")[:200]

    info = schops.get_schematic_info()
    refs = {item["reference"] for item in info["components"]}
    assert {"F1", "U1", "R1", "D1"} <= refs

    reloaded = schops.load_schematic(str(schematic))
    assert reloaded["component_count"] >= 4

    extra = schops.add_component(
        "Device:C",
        reference="C1",
        value="100nF",
        position=(101.60, 88.90),
        footprint="Capacitor_SMD:C_0603_1608Metric",
    )
    assert extra["success"]
    schops.add_label("TEST_NET", (104.14, 88.90))
    saved = schops.save_schematic(str(schematic))
    assert saved["success"]

    schops.load_schematic(str(schematic))
    after = schops.list_components()
    assert any(item["reference"] == "C1" for item in after["components"])

    connectivity = schops.inspect_connectivity()
    assert connectivity["success"]
    assert connectivity["rules"]["wire_crossing_is_not_a_connection"] is True
    fuse_to_regulator = False
    for _name, pins in connectivity["nets"].items():
        if "U1.1" in pins and any(item.startswith("F1.") for item in pins):
            fuse_to_regulator = True
    assert fuse_to_regulator, connectivity["nets"]

    erc = schops.run_erc()
    assert erc["success"]
    assert "report_path" in erc

    bom = schops.export_bom()
    assert bom["success"]
    assert Path(bom["path"]).is_file()

    net = schops.export_netlist()
    assert net["success"]
    assert Path(net["path"]).is_file()


def test_remove_component_requires_confirm() -> None:
    create_mcp_test_project(name="smoke-tmp", location="user", overwrite=True)
    try:
        schops.remove_component("F1", confirm=False)
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
