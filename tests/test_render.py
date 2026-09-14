from __future__ import annotations

import json
from pathlib import Path

import pymupdf

from kicad_ai.config import get_workspace, load_env
from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import setup_logging
from kicad_ai.render.common import file_sha256, read_json
from kicad_ai.render.models import model_exists, models_in_text
from kicad_ai.render.pcb import render_pcb, render_pcb_3d
from kicad_ai.render.project_render import get_render_report, render_project
from kicad_ai.render.raster import png_ok
from kicad_ai.render.schematic import render_schematic
from kicad_ai.validate import resolve_kicad_files

MCP_TEST = Path("projects/examples/mcp-test")


def setup_module() -> None:
    load_env()
    setup_logging()
    require_kicad()


def _project() -> Path:
    path = get_workspace() / MCP_TEST
    assert path.is_dir()
    return path


def test_schematic_exists() -> None:
    files = resolve_kicad_files(_project())
    assert files["sch"] is not None
    assert files["sch"].is_file()
    text = files["sch"].read_text(encoding="utf-8", errors="replace")
    assert "(kicad_sch" in text


def test_schematic_render() -> None:
    result = render_schematic(_project(), view="full", quality="preview", force=True)
    assert result["skipped"] is False
    assert result["ok"] is True
    assert result["status"] == "PASS"
    assert result["backend"] == "kicad_cli"
    assert result["artifacts"]


def test_svg_generated() -> None:
    result = render_schematic(_project(), view="full", quality="preview", force=True)
    svg_items = [item for item in result["artifacts"] if item["format"] == "svg"]
    assert svg_items
    path = get_workspace() / svg_items[0]["path"]
    assert path.is_file()
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "<svg" in text
    assert "viewBox=" in text
    doc = pymupdf.open(stream=path.read_bytes(), filetype="svg")
    try:
        assert doc.page_count >= 1
        rect = doc[0].rect
        assert rect.width > 0 and rect.height > 0
    finally:
        doc.close()
    assert path.stat().st_size > 1000


def test_png_generated() -> None:
    result = render_schematic(_project(), view="full", quality="preview", force=True)
    png_items = [item for item in result["artifacts"] if item["format"] == "png"]
    assert png_items
    path = get_workspace() / png_items[0]["path"]
    assert png_ok(path)
    assert path.stat().st_size > 0


def test_pcb_render() -> None:
    result = render_pcb(_project(), side="top", force=True)
    files = resolve_kicad_files(_project())
    if files["pcb"] is None:
        assert result["skipped"] is True
        assert result["status"] == "SKIPPED"
        assert "no .kicad_pcb" in result["reason"]
        assert result["artifacts"] == []
        return
    assert result["ok"] is True
    assert any(item["format"] == "png" for item in result["artifacts"])


def test_3d_render() -> None:
    result = render_pcb_3d(_project(), camera="isometric", force=True)
    files = resolve_kicad_files(_project())
    if files["pcb"] is None:
        assert result["skipped"] is True
        assert result["status"] == "SKIPPED"
        assert "no .kicad_pcb" in result["reason"]
        return
    assert result["ok"] is True
    png_items = [item for item in result["artifacts"] if item["format"] == "png"]
    assert png_items
    assert png_ok(get_workspace() / png_items[0]["path"])


def test_missing_3d_model_is_warning() -> None:
    text = '(footprint "x" (model "${KICAD10_3DMODEL_DIR}/__missing_part.wrl"))'
    paths = models_in_text(text)
    assert paths == ["${KICAD10_3DMODEL_DIR}/__missing_part.wrl"]
    assert model_exists(paths[0]) is False
    result = render_pcb_3d(_project(), camera="top", force=True)
    assert result["status"] in {"PASS", "SKIPPED"}
    # Missing models must not crash the pipeline.
    assert result.get("success") is True


def test_render_report() -> None:
    report = render_project(_project(), quality="preview", force=True, include_views=True)
    assert report["result"] in {"PASS", "FAIL"}
    assert "schematic" in report
    path = get_workspace() / report["report"]
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["result"] == report["result"]
    loaded = get_render_report(_project())
    assert loaded["success"] is True
    if report["schematic"]:
        assert loaded["schematic"].get("png")


def test_source_hash() -> None:
    sch = resolve_kicad_files(_project())["sch"]
    assert sch is not None
    digest = file_sha256(sch)
    first = render_schematic(_project(), view="full", quality="preview", force=True)
    assert first["source_hash"] == digest
    meta = read_json(get_workspace() / "renders" / sch.stem / "schematic" / "full.meta.json")
    assert meta is not None
    assert meta["source_hash"] == digest
    second = render_schematic(_project(), view="full", quality="preview", force=False)
    assert second["reused"] is True
    assert second["source_hash"] == digest
