"""Abstract renderer plus future backends. Only KiCadRenderer is implemented."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Renderer(ABC):
    """Stable interface so Blender/AI backends can be added later without MCP rewrites."""

    name: str = "abstract"

    @abstractmethod
    def render_schematic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def render_pcb(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def render_3d(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class KiCadRenderer(Renderer):
    """Production backend: kicad-cli SVG/PDF/3D. No screenshots, no AI images."""

    name = "kicad_cli"

    def render_schematic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from kicad_ai.render.schematic import render_schematic

        return render_schematic(*args, **kwargs)

    def render_pcb(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from kicad_ai.render.pcb import render_pcb

        return render_pcb(*args, **kwargs)

    def render_3d(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from kicad_ai.render.pcb import render_pcb_3d

        return render_pcb_3d(*args, **kwargs)


class BlenderRenderer(Renderer):
    name = "blender"

    def render_schematic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Blender renderer is not installed")

    def render_pcb(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Blender renderer is not installed")

    def render_3d(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Blender renderer is not installed")


class AIRenderer(Renderer):
    name = "ai"

    def render_schematic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("AI image generation is not used for engineering renders")

    def render_pcb(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("AI image generation is not used for engineering renders")

    def render_3d(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("AI image generation is not used for engineering renders")
