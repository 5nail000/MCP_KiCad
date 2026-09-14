"""Reusable SKiDL circuit blocks. They never write KiCad project schematics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from skidl_lab.blocks.led_indicator import build as build_led_indicator
from skidl_lab.blocks.rail_12v_5v import build as build_rail_12v_5v

BLOCKS: dict[str, Callable[..., Any]] = {
    "led_indicator": build_led_indicator,
    "rail_12v_5v": build_rail_12v_5v,
}

__all__ = ["BLOCKS", "build_led_indicator", "build_rail_12v_5v"]
