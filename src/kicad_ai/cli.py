"""Command-line entry points: doctor, MCP, backup, open-kicad, example project."""

from __future__ import annotations

import argparse
import sys

from kicad_ai.config import get_workspace, load_env
from kicad_ai.detect import require_kicad
from kicad_ai.logging_setup import get_logger, setup_logging
from kicad_ai.paths import assert_allowed


def _boot() -> None:
    load_env()
    setup_logging()


def doctor_main(argv: list[str] | None = None) -> int:
    _boot()
    from kicad_ai.doctor import print_doctor

    return print_doctor()


def mcp_main(argv: list[str] | None = None) -> int:
    _boot()
    from kicad_ai.mcp.server import main as start_mcp

    start_mcp()
    return 0


def backup_main(target: str) -> int:
    _boot()
    from kicad_ai.backup import backup_project

    dest = backup_project(target)
    get_logger().info("Backup stored at %s", dest)
    return 0


def open_kicad_main(project: str | None) -> int:
    _boot()
    install = require_kicad()
    workspace = get_workspace()
    if project:
        path = assert_allowed(project, write=False)
    else:
        default = workspace / "projects" / "examples" / "mcp-test" / "mcp-test.kicad_pro"
        path = default
    if path.is_dir():
        matches = list(path.glob("*.kicad_pro"))
        if not matches:
            raise FileNotFoundError(f"No .kicad_pro in {path}")
        path = matches[0]
    logger = get_logger()
    logger.info("Opening %s with %s", path, install.kicad_exe)
    import subprocess

    subprocess.Popen([str(install.kicad_exe), str(path)], cwd=str(path.parent))
    return 0


def example_main() -> int:
    _boot()
    from kicad_ai.example_circuit import create_mcp_test_project

    result = create_mcp_test_project()
    get_logger().info("Example project: %s", result.get("project", result))
    return 0


def validate_main(target: str, *, run_skidl: bool, skidl_block: str | None) -> int:
    _boot()
    from kicad_ai.validate import validate_project

    logger = get_logger()
    report = validate_project(target, run_skidl=run_skidl, skidl_block=skidl_block)
    logger.info("validate verdict=%s", report.get("verdict"))
    for name, check in report.get("checks", {}).items():
        logger.info(
            "  %s status=%s skipped=%s ok=%s",
            name,
            check.get("status"),
            check.get("skipped"),
            check.get("ok"),
        )
        reason = check.get("reason")
        if reason:
            logger.info("  %s reason=%s", name, reason)
        violations = check.get("violations") or []
        if violations:
            logger.info("  %s violations=%s", name, len(violations))
            for item in violations[:20]:
                logger.info("    %s %s", item.get("severity"), item.get("description"))
    return 0 if report.get("ok") else 1


def skidl_erc_main(block: str) -> int:
    _boot()
    from kicad_ai.skidl_runtime import run_block_erc

    logger = get_logger()
    result = run_block_erc(block)
    logger.info("SKiDL ERC block=%s status=%s errors=%s warnings=%s", block, result.get("status"), result.get("errors"), result.get("warnings"))
    for message in result.get("messages") or []:
        logger.info("  %s", message)
    return 0 if result.get("ok") else 1


def render_main(kind: str, target: str, **opts: object) -> int:
    _boot()
    from kicad_ai.render.project_render import format_banner, render_project
    from kicad_ai.render.pcb import render_pcb, render_pcb_3d
    from kicad_ai.render.schematic import render_schematic

    logger = get_logger()
    force = bool(opts.get("force"))
    theme = opts.get("theme") if isinstance(opts.get("theme"), str) else None
    quality = opts.get("quality") if isinstance(opts.get("quality"), str) else None
    if kind == "project":
        report = render_project(target, force=force, theme=theme, quality=quality)
        for line in format_banner(report).splitlines():
            logger.info("%s", line)
        logger.info("report=%s", report.get("report"))
        return 0 if report.get("ok") else 1
    if kind == "schematic":
        result = render_schematic(
            target,
            view=str(opts.get("view") or "full"),
            theme=theme,
            quality=quality,
            force=force,
        )
    elif kind == "pcb":
        result = render_pcb(target, side=str(opts.get("side") or "top"), force=force)
    else:
        result = render_pcb_3d(target, camera=str(opts.get("camera") or "isometric"), force=force)
    logger.info("render status=%s skipped=%s", result.get("status"), result.get("skipped"))
    if result.get("reason"):
        logger.info("reason=%s", result["reason"])
    for item in result.get("artifacts") or []:
        logger.info("artifact %s %s %s", item.get("type"), item.get("format"), item.get("path"))
    for warning in result.get("warnings") or []:
        logger.warning("%s", warning)
    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kicad-ai", description="KiCad AI workspace helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check KiCad, Python, uv, git, MCP")
    sub.add_parser("mcp", help="Start the sandboxed MCP server on stdio")
    sub.add_parser("example", help="Create/rebuild projects/examples/mcp-test")
    backup = sub.add_parser("backup", help="Backup a project directory")
    backup.add_argument("target")
    open_cmd = sub.add_parser("open", help="Open a project in KiCad GUI")
    open_cmd.add_argument("project", nargs="?")
    validate = sub.add_parser("validate", help="Run KiCad ERC and DRC (DRC skipped if no PCB)")
    validate.add_argument("target")
    validate.add_argument("--skidl", action="store_true", help="Also run SKiDL ERC on a lab block")
    validate.add_argument("--skidl-block", default="led_indicator")
    skidl_erc = sub.add_parser("skidl-erc", help="Run SKiDL ERC on a skidl_lab block")
    skidl_erc.add_argument("block")
    render = sub.add_parser("render", help="Render schematic + PCB/3D (SKIPPED if no board)")
    render.add_argument("target")
    render.add_argument("--force", action="store_true")
    render.add_argument("--theme", choices=["light", "dark"])
    render.add_argument("--quality", default="docs")
    sch = sub.add_parser("render-schematic", help="kicad-cli sch export svg/pdf + PNG")
    sch.add_argument("target")
    sch.add_argument("--view", default="full")
    sch.add_argument("--theme", choices=["light", "dark"])
    sch.add_argument("--quality", default="docs")
    sch.add_argument("--force", action="store_true")
    pcb = sub.add_parser("render-pcb", help="kicad-cli pcb export svg (2D)")
    pcb.add_argument("target")
    pcb.add_argument("--side", default="top", choices=["top", "bottom", "both"])
    pcb.add_argument("--force", action="store_true")
    three = sub.add_parser("render-3d", help="kicad-cli pcb render (3D PNG)")
    three.add_argument("target")
    three.add_argument("--camera", default="isometric", choices=["top", "bottom", "front", "isometric"])
    three.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    _boot()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor_main()
        if args.command == "mcp":
            return mcp_main()
        if args.command == "backup":
            return backup_main(args.target)
        if args.command == "open":
            return open_kicad_main(args.project)
        if args.command == "example":
            return example_main()
        if args.command == "validate":
            return validate_main(args.target, run_skidl=args.skidl, skidl_block=args.skidl_block)
        if args.command == "skidl-erc":
            return skidl_erc_main(args.block)
        if args.command == "render":
            return render_main("project", args.target, force=args.force, theme=args.theme, quality=args.quality)
        if args.command == "render-schematic":
            return render_main(
                "schematic",
                args.target,
                view=args.view,
                theme=args.theme,
                quality=args.quality,
                force=args.force,
            )
        if args.command == "render-pcb":
            return render_main("pcb", args.target, side=args.side, force=args.force)
        if args.command == "render-3d":
            return render_main("3d", args.target, camera=args.camera, force=args.force)
    except Exception as exc:  # noqa: BLE001
        from kicad_ai.logging_setup import log_exception

        log_exception(get_logger(), operation=args.command, error=exc, tool="cli")
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
