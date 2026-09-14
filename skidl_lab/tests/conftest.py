from __future__ import annotations

from kicad_ai.config import load_env
from kicad_ai.logging_setup import setup_logging
from kicad_ai.skidl_runtime import configure

load_env()
setup_logging()
configure()
