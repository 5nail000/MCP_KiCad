"""uv run python scripts/render_3d.py <project> [--camera isometric]"""

from __future__ import annotations

import argparse

from kicad_ai.cli import render_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render KiCad 3D viewer PNG via kicad-cli pcb render")
    parser.add_argument("target", nargs="?", default="projects/examples/mcp-test")
    parser.add_argument("--camera", default="isometric", choices=["top", "bottom", "front", "isometric"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return render_main("3d", args.target, camera=args.camera, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
