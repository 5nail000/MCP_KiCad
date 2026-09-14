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
    except Exception as exc:  # noqa: BLE001
        from kicad_ai.logging_setup import log_exception

        log_exception(get_logger(), operation=args.command, error=exc, tool="cli")
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
