"""uv run python scripts/render_project.py [project]"""

from __future__ import annotations

import argparse

from kicad_ai.cli import render_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render schematic and PCB/3D if present")
    parser.add_argument("target", nargs="?", default="projects/examples/mcp-test")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument("--quality", default="docs")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return render_main("project", args.target, force=args.force, theme=args.theme, quality=args.quality)


if __name__ == "__main__":
    raise SystemExit(main())
