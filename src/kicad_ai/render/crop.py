"""Crop KiCad SVG to the drawing bounding box with a configurable millimetre margin.

Does not invent geometry: only tightens viewBox around existing paths and text.
"""

from __future__ import annotations

import re
from pathlib import Path

from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed

_NUM = re.compile(r"[-+]?(?:\d+\.\d+|\d+\.|\.\d+|\d+)")
_PAIR_ATTR = re.compile(r'\b(?P<axis>[xy])="(?P<val>[-+0-9.]+)"', re.I)


def content_bbox(svg_text: str) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for match in _PAIR_ATTR.finditer(svg_text):
        value = float(match.group("val"))
        if match.group("axis").lower() == "x":
            xs.append(value)
        else:
            ys.append(value)
    for d_attr in re.finditer(r'\bd="([^"]*)"', svg_text, re.I | re.S):
        nums = [float(item) for item in _NUM.findall(d_attr.group(1))]
        for index in range(0, len(nums) - 1, 2):
            xs.append(nums[index])
            ys.append(nums[index + 1])
    for cx in re.finditer(r'\bcx="([-+0-9.]+)"', svg_text, re.I):
        xs.append(float(cx.group(1)))
    for cy in re.finditer(r'\bcy="([-+0-9.]+)"', svg_text, re.I):
        ys.append(float(cy.group(1)))
    if not xs or not ys:
        return None
    # Extra room for text baseline vs glyph box (KiCad font ~1.3mm).
    pad = 2.0
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def apply_viewbox(
    svg_text: str,
    bbox: tuple[float, float, float, float],
    *,
    margin_mm: float,
) -> str:
    min_x, min_y, max_x, max_y = bbox
    min_x -= margin_mm
    min_y -= margin_mm
    max_x += margin_mm
    max_y += margin_mm
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    replacement = (
        f'width="{width:.4f}mm" height="{height:.4f}mm" '
        f'viewBox="{min_x:.4f} {min_y:.4f} {width:.4f} {height:.4f}"'
    )
    updated, count = re.subn(
        r'width="[^"]*"\s+height="[^"]*"\s+viewBox="[^"]*"',
        replacement,
        svg_text,
        count=1,
    )
    if count == 0:
        updated = re.sub(r"<svg\b", f"<svg {replacement}", svg_text, count=1)
    return updated


def crop_svg_file(path: Path, *, margin_mm: float, clip: tuple[float, float, float, float] | None = None) -> dict[str, float]:
    dest = assert_allowed(path, write=True)
    text = dest.read_text(encoding="utf-8", errors="replace")
    bbox = clip or content_bbox(text)
    logger = get_logger()
    if bbox is None:
        logger.warning("SVG crop: no drawing coordinates in %s; leaving page size", dest)
        return {"cropped": 0.0}
    dest.write_text(apply_viewbox(text, bbox, margin_mm=margin_mm), encoding="utf-8")
    logger.info("SVG crop %s bbox=%.1f,%.1f,%.1f,%.1f margin=%.1fmm", dest.name, *bbox, margin_mm)
    return {
        "min_x": bbox[0],
        "min_y": bbox[1],
        "max_x": bbox[2],
        "max_y": bbox[3],
        "margin_mm": margin_mm,
    }


def apply_dark_presentation(svg_text: str) -> str:
    """Invert only black ink onto a dark background. Does not change geometry."""
    text = svg_text
    text = re.sub(r"stroke:#000000", "stroke:#E6E6E6", text, flags=re.I)
    text = re.sub(r"fill:#000000", "fill:#E6E6E6", text, flags=re.I)
    if "id=\"kicad-ai-dark-bg\"" not in text:
        text = text.replace(
            "<svg",
            '<svg style="background-color:#1B1B1B"',
            1,
        )
    return text
