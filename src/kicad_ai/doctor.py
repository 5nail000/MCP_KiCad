"""Environment diagnostics with human-readable [OK]/[FAIL] output."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from kicad_ai import __version__
from kicad_ai.config import get_workspace, load_env
from kicad_ai.detect import find_kicad
from kicad_ai.logging_setup import get_logger, setup_logging


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None
    warn: bool = False

    def render(self) -> str:
        if self.ok:
            tag = "[WARN]" if self.warn else "[OK]"
        else:
            tag = "[FAIL]"
        line = f"{tag} {self.name}: {self.detail}"
        if not self.ok and self.fix:
            line += f"\n      Fix: {self.fix}"
        return line


def _check_kicad() -> Check:
    install = find_kicad()
    if install is None:
        return Check(
            "KiCad",
            False,
            "KiCad executable not found",
            "Install KiCad 10.x (winget install --id KiCad.KiCad --exact) or set KICAD_EXE in .env",
        )
    symbols_ok = install.symbol_dir.is_dir() and any(install.symbol_dir.glob("*.kicad_sym"))
    footprints_ok = install.footprint_dir.is_dir()
    detail = (
        f"{install.version} exe={install.kicad_exe} cli={install.kicad_cli} "
        f"symbols={'yes' if symbols_ok else 'MISSING'} footprints={'yes' if footprints_ok else 'MISSING'}"
    )
    ok = symbols_ok and footprints_ok and install.kicad_cli.is_file()
    return Check(
        "KiCad",
        ok,
        detail,
        None if ok else "Reinstall KiCad 10 with official symbol and footprint libraries",
    )


def _check_python() -> Check:
    ver = sys.version.split()[0]
    ok = sys.version_info[:2] == (3, 12)
    return Check(
        "Python",
        ok,
        f"{ver} ({sys.executable})",
        "This project pins Python 3.12 via .python-version / uv. Run: uv sync",
    )


def _check_uv() -> Check:
    path = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv.exe")
    exe = Path(path)
    if not exe.is_file():
        return Check("uv", False, "uv not found", "Install uv from https://docs.astral.sh/uv/")
    try:
        result = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=20)
        detail = (result.stdout or result.stderr).strip() + f" ({exe})"
        return Check("uv", result.returncode == 0, detail)
    except OSError as exc:
        return Check("uv", False, str(exc), "Reinstall uv")


def _check_git() -> Check:
    path = shutil.which("git")
    if not path:
        return Check("Git", False, "git not found", "Install Git for Windows")
    result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=20)
    return Check("Git", result.returncode == 0, (result.stdout or "").strip())


def _check_skidl() -> Check:
    try:
        from importlib.metadata import version as pkg_version

        from kicad_ai.skidl_runtime import configure

        configure()
        import skidl

        dist = pkg_version("skidl")
        attr = getattr(skidl, "__version__", "unknown")
        from skidl import KICAD10, get_default_tool

        tool = get_default_tool()
        detail = f"package {dist} (module attr {attr}) tool={tool} KICAD10={KICAD10}"
        ok = str(tool) == str(KICAD10)
        return Check("SKiDL", ok, detail, None if ok else "SKiDL default tool is not KICAD10")
    except Exception as exc:  # noqa: BLE001
        return Check("SKiDL", False, str(exc), "Run: uv sync")


def _check_kicad_sch_api() -> Check:
    try:
        import kicad_sch_api as ksa
        from importlib.metadata import version as pkg_version

        dist = pkg_version("kicad-sch-api")
        attr = getattr(ksa, "__version__", "unknown")
        return Check("kicad-sch-api", True, f"package {dist} (module attr {attr})")
    except Exception as exc:  # noqa: BLE001
        return Check("kicad-sch-api", False, str(exc), "Run: uv sync")


def _check_mcp_config(workspace: Path) -> Check:
    config_path = workspace / ".cursor" / "mcp.json"
    if not config_path.is_file():
        return Check("MCP configuration", False, f"missing {config_path}", "Create .cursor/mcp.json as documented in README")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Check("MCP configuration", False, f"invalid JSON: {exc}")
    servers = data.get("mcpServers") or data.get("mcp") or {}
    if "kicad" not in servers:
        return Check("MCP configuration", False, "mcpServers.kicad is missing")
    server = servers["kicad"]
    args = server.get("args") or []
    command = str(server.get("command") or "")
    valid_entry = "start-mcp" in args or "kicad_ai.mcp.server" in args
    if not valid_entry:
        return Check("MCP configuration", False, f"unexpected command/args: {command} {args}")
    return Check("MCP configuration", True, str(config_path))


def _check_workspace(workspace: Path) -> Check:
    required = ["projects", "projects/examples", "projects/user", "docs", "src/kicad_ai", "skidl_lab"]
    missing = [name for name in required if not (workspace / name).exists()]
    writable = os.access(workspace, os.W_OK)
    if missing:
        return Check("workspace", False, f"missing {missing}", "Re-run scripts/setup.ps1")
    if not writable:
        return Check("workspace", False, f"not writable: {workspace}")
    return Check("workspace", True, str(workspace))


def _cli_help(*args: str) -> tuple[bool, str]:
    install = find_kicad()
    if install is None:
        return False, "KiCad CLI not found"
    try:
        result = subprocess.run(
            [str(install.kicad_cli), *args, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    text = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, text.splitlines()[0] if text else f"exit {result.returncode}"


def _render_checks() -> list[Check]:
    checks: list[Check] = []
    ok, detail = _cli_help("sch", "export", "svg")
    checks.append(
        Check(
            "Schematic renderer",
            ok,
            detail if ok else "kicad-cli sch export svg missing",
            None if ok else "Install KiCad 10 with kicad-cli schematic SVG export",
        )
    )
    ok, detail = _cli_help("sch", "export", "pdf")
    checks.append(
        Check(
            "PDF export",
            ok,
            detail if ok else "kicad-cli sch export pdf missing",
            None if ok else "Install KiCad 10 with schematic PDF export",
        )
    )
    ok, detail = _cli_help("pcb", "export", "svg")
    checks.append(
        Check(
            "PCB renderer",
            ok,
            detail if ok else "kicad-cli pcb export svg missing",
            None if ok else "Install KiCad 10 with pcb SVG export",
        )
    )
    ok, detail = _cli_help("pcb", "render")
    checks.append(
        Check(
            "3D renderer",
            ok,
            detail if ok else "kicad-cli pcb render missing",
            None if ok else "Upgrade KiCad 10 so `kicad-cli pcb render` is available (PNG/JPEG 3D view)",
        )
    )
    install = find_kicad()
    if install is None:
        checks.append(Check("3D model libraries", False, "KiCad not found", "Install KiCad 10"))
    elif install.threed_dir.is_dir() and any(install.threed_dir.glob("*.3dshapes")):
        count = len(list(install.threed_dir.glob("*.3dshapes")))
        checks.append(Check("3D model libraries", True, f"{count} libraries in {install.threed_dir}"))
    else:
        checks.append(
            Check(
                "3D model libraries",
                True,
                f"missing or empty: {getattr(install, 'threed_dir', None)}",
                "Reinstall KiCad 10 with 3D model packages",
                True,
            )
        )
    try:
        import pymupdf  # noqa: F401
        from PIL import Image  # noqa: F401

        checks.append(Check("SVG support", True, "KiCad SVG export + PyMuPDF rasterizer"))
        checks.append(Check("PNG conversion", True, "PyMuPDF + Pillow"))
    except Exception as exc:  # noqa: BLE001
        checks.append(
            Check(
                "PNG conversion",
                False,
                str(exc),
                "Run: uv sync  (needs pymupdf and pillow)",
            )
        )
        checks.append(Check("SVG support", ok, "KiCad can export SVG; PNG rasterizer missing"))
    return checks


def run_checks() -> list[Check]:
    workspace = load_env()
    setup_logging(workspace=workspace)
    return [
        _check_kicad(),
        _check_python(),
        _check_uv(),
        _check_git(),
        _check_kicad_sch_api(),
        _check_skidl(),
        _check_mcp_config(workspace),
        _check_workspace(workspace),
        *_render_checks(),
        Check("kicad-ai", True, __version__),
    ]


def doctor_text() -> tuple[str, int]:
    checks = run_checks()
    lines = [item.render() for item in checks]
    failed = [item for item in checks if not item.ok]
    code = 1 if failed else 0
    summary = f"doctor: {len(checks) - len(failed)}/{len(checks)} checks passed"
    lines.append(summary)
    return "\n".join(lines), code


def print_doctor() -> int:
    logger = get_logger()
    text, code = doctor_text()
    for line in text.splitlines():
        if line.startswith("[FAIL]"):
            logger.error(line)
        elif line.startswith("[WARN]"):
            logger.warning(line)
        else:
            logger.info(line)
    return code
