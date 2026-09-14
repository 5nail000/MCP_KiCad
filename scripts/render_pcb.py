"""uv run python scripts/render_pcb.py <project> [--side top]"""

from __future__ import annotations

import argparse

from kicad_ai.cli import render_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a KiCad PCB 2D view via kicad-cli")
    parser.add_argument("target", nargs="?", default="projects/examples/mcp-test")
    parser.add_argument("--side", default="top", choices=["top", "bottom", "both"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return render_main("pcb", args.target, side=args.side, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
