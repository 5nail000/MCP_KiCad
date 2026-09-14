"""Rasterize KiCad SVG/PDF with PyMuPDF. Does not draw the schematic itself."""

from __future__ import annotations

from pathlib import Path

from kicad_ai.logging_setup import get_logger
from kicad_ai.paths import assert_allowed


def svg_to_png(svg_path: Path, png_path: Path, *, dpi: int, background: str = "transparent") -> Path:
    import pymupdf
    from PIL import Image

    src = assert_allowed(svg_path, write=False)
    dest = assert_allowed(png_path, write=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger = get_logger()
    data = src.read_bytes()
    doc = pymupdf.open(stream=data, filetype="svg")
    try:
        page = doc[0]
        zoom = max(dpi, 72) / 72.0
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
        pixmap.save(str(dest))
    finally:
        doc.close()
    with Image.open(dest) as image:
        image.load()
        if image.width < 1 or image.height < 1:
            raise ValueError(f"PNG raster is empty: {dest}")
        rgba = image.convert("RGBA")
        if background == "white":
            canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            canvas.alpha_composite(rgba)
            canvas.save(dest)
        elif background == "opaque":
            canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            canvas.alpha_composite(rgba)
            canvas.convert("RGB").save(dest)
        logger.info("PNG %s %sx%s dpi=%s bg=%s", dest.name, rgba.width, rgba.height, dpi, background)
    return dest


def pdf_ok(path: Path) -> bool:
    import pymupdf

    src = assert_allowed(path, write=False)
    doc = pymupdf.open(src)
    try:
        return doc.page_count >= 1
    finally:
        doc.close()


def png_ok(path: Path) -> bool:
    from PIL import Image

    src = assert_allowed(path, write=False)
    with Image.open(src) as image:
        image.load()
        return image.format == "PNG" and image.width > 0 and image.height > 0
