"""Thin wrappers around the real kicad-cli.exe (ERC, DRC, BOM, netlist, schematic upgrade)."""

from __future__ import annotations

import json
import subprocess
import re
from pathlib import Path
from typing import Any

from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed


class KiCadCliError(RuntimeError):
    def __init__(self, message: str, *, stdout: str = "", stderr: str = "", returncode: int = 1):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def run_kicad_cli(args: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    install = require_kicad()
    logger = get_logger()
    command = [str(install.kicad_cli), *args]
    logger.info("kicad-cli: %s", " ".join(command))
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise KiCadCliError(f"kicad-cli timed out: {command}") from exc
    if result.returncode not in (0, 2):
        raise KiCadCliError(
            f"kicad-cli failed with code {result.returncode}: {result.stderr or result.stdout}",
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    return result


def upgrade_schematic(schematic: Path) -> None:
    path = assert_allowed(schematic, write=True)
    run_kicad_cli(["sch", "upgrade", str(path)])


def run_erc(schematic: Path, *, output: Path | None = None) -> dict[str, Any]:
    sch = assert_allowed(schematic, write=False)
    report = output or sch.with_suffix(".erc.json")
    report = assert_allowed(report, write=True)
    result = run_kicad_cli(
        [
            "sch",
            "erc",
            "--format",
            "json",
            "--severity-warning",
            "--severity-error",
            "--output",
            str(report),
            str(sch),
        ]
    )
    payload: dict[str, Any] = {
        "success": True,
        "returncode": result.returncode,
        "report_path": str(report),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "violations": [],
    }
    if report.is_file():
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            payload["report"] = data
            payload["violations"] = _extract_violations(data)
        except json.JSONDecodeError:
            payload["report_text"] = report.read_text(encoding="utf-8", errors="replace")
    payload["ok"] = result.returncode == 0 and not payload["violations"]
    payload["skipped"] = False
    payload["status"] = "PASS" if payload["ok"] else "FAIL"
    payload["engine"] = "kicad-cli sch erc"
    return payload


def export_bom(schematic: Path, *, output: Path | None = None) -> dict[str, Any]:
    sch = assert_allowed(schematic, write=False)
    bom = output or sch.with_name(sch.stem + ".csv")
    bom = assert_allowed(bom, write=True)
    result = run_kicad_cli(["sch", "export", "bom", "--output", str(bom), str(sch)])
    text = bom.read_text(encoding="utf-8", errors="replace") if bom.is_file() else ""
    return {
        "success": True,
        "path": str(bom),
        "returncode": result.returncode,
        "preview": "\n".join(text.splitlines()[:40]),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def export_netlist(schematic: Path, *, output: Path | None = None, fmt: str = "kicadsexpr") -> dict[str, Any]:
    sch = assert_allowed(schematic, write=False)
    net = output or sch.with_suffix(".net")
    net = assert_allowed(net, write=True)
    result = run_kicad_cli(
        ["sch", "export", "netlist", "--format", fmt, "--output", str(net), str(sch)]
    )
    return {
        "success": True,
        "path": str(net),
        "format": fmt,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_drc(pcb: Path, *, output: Path | None = None) -> dict[str, Any]:
    board = assert_allowed(pcb, write=False)
    if board.suffix != ".kicad_pcb":
        raise ValueError("DRC input must be a .kicad_pcb file")
    if not board.is_file():
        raise FileNotFoundError(f"PCB not found: {board}")
    report = output or board.with_suffix(".drc.json")
    report = assert_allowed(report, write=True)
    args = [
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-warning",
        "--severity-error",
        "--output",
        str(report),
        str(board),
    ]
    schematic = board.with_suffix(".kicad_sch")
    if schematic.is_file():
        args.insert(-1, "--schematic-parity")
    result = run_kicad_cli(args)
    payload: dict[str, Any] = {
        "success": True,
        "skipped": False,
        "status": "FAIL",
        "returncode": result.returncode,
        "report_path": str(report),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "violations": [],
        "engine": "kicad-cli pcb drc",
    }
    if report.is_file():
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            payload["report"] = data
            payload["violations"] = _extract_violations(data)
            payload["violations"].extend(_extract_unconnected(data))
        except json.JSONDecodeError:
            payload["report_text"] = report.read_text(encoding="utf-8", errors="replace")
    payload["ok"] = result.returncode == 0 and not payload["violations"]
    payload["status"] = "PASS" if payload["ok"] else "FAIL"
    return payload


def skipped_drc(*, reason: str, pcb: Path | None = None) -> dict[str, Any]:
    """Real skip when there is no PCB — not a fake PASS."""
    return {
        "success": True,
        "skipped": True,
        "ok": True,
        "status": "SKIPPED",
        "reason": reason,
        "pcb": str(pcb) if pcb else None,
        "violations": [],
        "engine": "kicad-cli pcb drc",
    }


def parse_kicad_netlist(text: str) -> dict[str, list[str]]:
    """Parse kicad-cli sexpr netlist into {net_name: ['R1.1', ...]}."""
    nets: dict[str, list[str]] = {}
    blocks = re.split(r"\(net\s+\(code", text)
    for block in blocks[1:]:
        name_match = re.search(r'\(name "([^"]*)"\)', block)
        if not name_match:
            continue
        name = name_match.group(1)
        pins = [f"{ref}.{pin}" for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', block)]
        nets[name] = pins
    return nets


def nets_from_schematic(schematic: Path) -> dict[str, list[str]]:
    exported = export_netlist(schematic)
    path = Path(exported["path"])
    return parse_kicad_netlist(path.read_text(encoding="utf-8", errors="replace"))


def _extract_violations(data: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for key in ("violations", "sheets"):
            if key in data:
                found.extend(_extract_violations(data[key]))
        if "severity" in data and ("description" in data or "type" in data or "message" in data):
            found.append(
                {
                    "severity": data.get("severity"),
                    "type": data.get("type") or data.get("name"),
                    "description": data.get("description") or data.get("message"),
                }
            )
    elif isinstance(data, list):
        for item in data:
            found.extend(_extract_violations(item))
    return found


def _extract_unconnected(data: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not isinstance(data, dict):
        return found
    for item in data.get("unconnected_items") or []:
        if not isinstance(item, dict):
            continue
        found.append(
            {
                "severity": item.get("severity") or "error",
                "type": item.get("type") or "unconnected_items",
                "description": item.get("description") or item.get("message") or "unconnected item",
            }
        )
    return found
