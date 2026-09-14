"""uv run python scripts/doctor.py"""

from __future__ import annotations

from kicad_ai.config import load_env
from kicad_ai.doctor import print_doctor
from kicad_ai.logging_setup import setup_logging


def main() -> int:
    load_env()
    setup_logging()
    return print_doctor()


if __name__ == "__main__":
    raise SystemExit(main())
