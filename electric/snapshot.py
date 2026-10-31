"""Offscreen rendering: single frames and contact sheets, no window needed.

Used by ``--snapshot`` and ``--sheet``, by the tests, and (next) by the
screensaver's preview box.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from electric import gpu, palettes, scene
from electric.config import Settings
from electric.show import Show


def standalone_context(preference: str = "high-performance"):
    gpu.choose(preference)
    import moderngl
    return moderngl.create_standalone_context(require=330)


class Offscreen:
    """A standalone context, a renderer and a colour buffer to read back."""

    def __init__(self, preference: str = "high-performance"):
        from electric.renderer import Renderer
        self.ctx = standalone_context(preference)
        self.renderer = Renderer(self.ctx)
        self.view = self.renderer.view()
        self._fbo = None

    @property
    def gpu_name(self) -> str:
        return self.ctx.info["GL_RENDERER"]

    def render(self, show: Show, settings: Settings, size) -> "pygame.Surface":
        import pygame
        size = tuple(size)
        if self._fbo is None or self._fbo.size != size:
            if self._fbo is not None:
                self._fbo.release()
            self._fbo = self.ctx.simple_framebuffer(size)
        self.view.resize(size, settings.resolution, settings.text)
        self.view.draw(show, settings, self._fbo)
        self._fbo.viewport = (0, 0, *size)
        data = self._fbo.read(components=3)
        return pygame.transform.flip(pygame.image.frombytes(data, size, "RGB"), False, True)


def frame(off: Offscreen, settings: Settings, size, seed: int, phase: float = 0.0):
    show = Show(settings, size[0] / size[1], seed=seed)
    show.phase = phase
    return off.render(show, settings, size)


def _label(surf, text):
    import pygame
    pygame.font.init()
    font = pygame.font.SysFont("segoeui,arial", max(12, surf.get_height() // 20), bold=True)
    img = font.render(text, True, (255, 255, 255))
    pygame.draw.rect(surf, (0, 0, 0), img.get_rect().inflate(12, 4).move(0, 0))
    surf.blit(img, (6, 2))


def sheet(off: Offscreen, settings: Settings, kind: str, seed: int, tile=(480, 270), columns=4):
    """A labelled grid. ``types``: each particle type alone. ``palettes``: one
    "All of them !" scene in every palette, then classic + tiling + blur, and
    dissymmetric tiling + text."""
    import pygame
    tiles = []
    if kind == "types":
        for t in range(1, len(scene.TYPES)):
            s = dataclasses.replace(settings, particle_type=scene.TYPES[t][0],
                                    random_count=False, new_palette_each_image=False)
            tiles.append((scene.TYPES[t][0], frame(off, s, tile, seed + t, 0.0)))
    elif kind == "palettes":
        base = dataclasses.replace(settings, particle_type="All", random_count=False,
                                   particle_count=5, new_palette_each_image=False)
        for name in palettes.NAMES:
            tiles.append((name, frame(off, dataclasses.replace(base, palette=name), tile, seed, 0.3)))
        tiles.append(("Classic + tiling + blur", frame(off, dataclasses.replace(
            base, palette="Neon", colours="classic", layout="tiling", blur=3), tile, seed, 0.3)))
        tiles.append(("Dissymmetric + text", frame(off, dataclasses.replace(
            base, palette="Greenland", layout="dissymmetric", text="ELECTRIC"), tile, seed, 0.3)))
    else:
        raise ValueError(f"unknown sheet {kind!r}: types or palettes")
    rows = -(-len(tiles) // columns)
    out = pygame.Surface((tile[0] * columns, tile[1] * rows))
    for i, (label, img) in enumerate(tiles):
        _label(img, label)
        out.blit(img, ((i % columns) * tile[0], (i // columns) * tile[1]))
    return out


def save(surf, path) -> Path:
    import pygame
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
    return path
