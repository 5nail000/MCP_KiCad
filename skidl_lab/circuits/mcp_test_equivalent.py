"""SKiDL twin of the mcp-test *architecture*.

This is not a second KiCad schematic. projects/examples/mcp-test remains authoritative.
"""

from __future__ import annotations

from skidl import Circuit

from skidl_lab.blocks.rail_12v_5v import build as build_rail


def build(circuit: Circuit | None = None) -> Circuit:
    return build_rail(circuit)
