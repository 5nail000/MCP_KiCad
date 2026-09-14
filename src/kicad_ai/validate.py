"""Unified KiCad ERC / DRC validation. Skip DRC when there is no PCB; never fake a PASS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kicad_ai.config import get_workspace
from kicad_ai.kicad_cli import run_drc as cli_run_drc
from kicad_ai.kicad_cli import run_erc as cli_run_erc
from kicad_ai.kicad_cli import skipped_drc
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed


def resolve_kicad_files(user_path: str | Path | None = None) -> dict[str, Path | None]:
    """Resolve .kicad_pro / .kicad_sch / .kicad_pcb from a project path or file."""
    if user_path is None:
        raise ValueError("Path to a KiCad project, schematic, PCB, or project directory is required")
    path = assert_allowed(user_path, write=False)
    if path.is_file():
        directory = path.parent
        stem = path.stem
    else:
        directory = path
        pros = sorted(directory.glob("*.kicad_pro"))
        if not pros:
            raise FileNotFoundError(f"No .kicad_pro in {directory}")
        stem = pros[0].stem

    pro = directory / f"{stem}.kicad_pro"
    sch = directory / f"{stem}.kicad_sch"
    pcb = directory / f"{stem}.kicad_pcb"
    return {
        "project_dir": directory,
        "pro": pro if pro.is_file() else None,
        "sch": sch if sch.is_file() else None,
        "pcb": pcb if pcb.is_file() else None,
    }


def validate_project(
    user_path: str | Path,
    *,
    run_skidl: bool = False,
    skidl_block: str | None = None,
) -> dict[str, Any]:
    """Run KiCad ERC and DRC. DRC is SKIPPED (not PASS) when no .kicad_pcb exists."""
    logger = get_logger()
    files = resolve_kicad_files(user_path)
    sch = files["sch"]
    pcb = files["pcb"]
    logger.info("validate_project sch=%s pcb=%s", sch, pcb)

    if sch is None:
        erc: dict[str, Any] = {
            "success": False,
            "ok": False,
            "skipped": False,
            "status": "FAIL",
            "reason": "no .kicad_sch",
            "violations": [],
            "engine": "kicad-cli sch erc",
        }
    else:
        erc = cli_run_erc(sch)

    if pcb is None:
        stem = sch.stem if sch is not None else (files["pro"].stem if files["pro"] is not None else None)
        expected = (files["project_dir"] / f"{stem}.kicad_pcb") if stem and files["project_dir"] else None
        drc = skipped_drc(reason="no .kicad_pcb in the KiCad project (board was never created)", pcb=expected)
    else:
        drc = cli_run_drc(pcb)

    python_checks = _python_sanity(files)
    skidl_result: dict[str, Any] | None = None
    if run_skidl:
        from kicad_ai.skidl_runtime import run_block_erc

        skidl_result = run_block_erc(skidl_block or "led_indicator")

    checks = {
        "erc": erc,
        "drc": drc,
        "python": python_checks,
    }
    if skidl_result is not None:
        checks["skidl"] = skidl_result

    blocking = [item for item in checks.values() if not item.get("skipped") and not item.get("ok")]
    skipped = [name for name, item in checks.items() if item.get("skipped")]
    verdict = "FAIL" if blocking else "PASS"
    payload = {
        "success": True,
        "ok": verdict == "PASS",
        "verdict": verdict,
        "source_of_truth": "KiCad schematic/PCB under projects/",
        "files": {key: (str(value) if value else None) for key, value in files.items()},
        "checks": checks,
        "skipped": skipped,
        "workspace": str(get_workspace()),
    }
    logger.info("validate_project verdict=%s skipped=%s", verdict, skipped)
    from kicad_ai.render.config import load_render_config

    cfg = load_render_config()
    if cfg.render_after_validation:
        if payload["ok"]:
            from kicad_ai.render.project_render import render_project as do_render

            payload["render"] = do_render(user_path)
        else:
            payload["render"] = {
                "skipped": True,
                "status": "SKIPPED",
                "reason": "validation FAIL; render_after_validation does not run on FAIL",
            }
    return payload


def _python_sanity(files: dict[str, Path | None]) -> dict[str, Any]:
    """In-process Python checks on the authoritative KiCad files (not a second schematic)."""
    sch = files["sch"]
    issues: list[str] = []
    if sch is None:
        return {
            "ok": False,
            "skipped": False,
            "status": "FAIL",
            "engine": "python",
            "issues": ["no .kicad_sch to inspect"],
        }
    text = sch.read_text(encoding="utf-8", errors="replace")
    if "(kicad_sch" not in text:
        issues.append("file does not look like a KiCad schematic")
    if files["pro"] is None:
        issues.append("missing .kicad_pro next to schematic")
    ok = not issues
    return {
        "ok": ok,
        "skipped": False,
        "status": "PASS" if ok else "FAIL",
        "engine": "python",
        "issues": issues,
        "has_pcb": files["pcb"] is not None,
    }
