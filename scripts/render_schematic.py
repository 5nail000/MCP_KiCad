"""uv run python scripts/render_schematic.py <project> [--view full]"""

from __future__ import annotations

import argparse

from kicad_ai.cli import render_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a KiCad schematic via kicad-cli")
    parser.add_argument("target", nargs="?", default="projects/examples/mcp-test")
    parser.add_argument("--view", default="full")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument("--quality", default="docs")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return render_main(
        "schematic",
        args.target,
        view=args.view,
        theme=args.theme,
        quality=args.quality,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
