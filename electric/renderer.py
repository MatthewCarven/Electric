"""The GPU side: a Show drawn in three passes (field, blur, palette).

``Renderer`` holds what every screen shares (shaders, the palette texture);
a ``View`` holds what one screen-sized area needs (its field textures, its
low-resolution frame, its text mask). One window can hold several views, one
per monitor, each drawn at its own ``origin``.

Works with any moderngl context: the pygame window's, or a standalone one for
snapshots, tests and the screensaver's preview box.
"""

from __future__ import annotations

from collections import OrderedDict
from importlib import resources

import moderngl

from electric import palettes, scene
from electric.config import Settings
from electric.show import Show

HEADER = "#version 330 core\n"
LAYOUT_INDEX = {"normal": 0, "tiling": 1, "dissymmetric": 2}
SPARE_LAYERS = 32           # for made-up palettes: two a screen, with plenty over


def _source(name: str) -> str:
    return resources.files("electric").joinpath("shaders", name).read_text(encoding="utf-8")


def _set(prog, name, value):
    """Set a uniform if the compiler kept it (unused ones are optimised away)."""
    member = prog.get(name, None)
    if member is not None:
        member.value = value


def render_size(screen_size, resolution: str):
    """The size the passes run at, for the "resolution" setting."""
    w, h = screen_size
    if resolution == "half":
        return max(1, w // 2), max(1, h // 2)
    if resolution == "640x480":
        return max(1, round(480 * w / h)), 480
    return w, h


class _Target:
    """A float texture and the framebuffer that draws into it."""

    def __init__(self, ctx, size):
        self.tex = ctx.texture(size, 4, dtype="f4")
        self.tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.tex.repeat_x = self.tex.repeat_y = False
        self.fbo = ctx.framebuffer(color_attachments=[self.tex])

    def release(self):
        self.fbo.release()
        self.tex.release()


class Renderer:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        vert = HEADER + _source("fullscreen.vert")

        def program(frag):
            prog = ctx.program(vertex_shader=vert, fragment_shader=HEADER + _source(frag))
            return prog, ctx.vertex_array(prog, [])

        self.field_prog, self.field_vao = program("field.frag")
        self.blur_prog, self.blur_vao = program("blur.frag")
        self.pal_prog, self.pal_vao = program("palette.frag")
        self.present_prog, self.present_vao = program("present.frag")
        self.overlay_prog, self.overlay_vao = program("overlay.frag")

        # One 256x1 layer per palette, mipmapped: the modern path averages
        # bands through the mips, and the 1x1 mip is each palette's mean colour.
        # The fixed palettes come first; made-up ones ("Random") get one of
        # the spare layers after them when first drawn.
        self._fixed = {pal: i for i, pal in enumerate(palettes.PALETTES)}
        self._made = OrderedDict()          # made-up palette -> layer, least recently drawn first
        spare = bytes(palettes.SIZE * 4 * SPARE_LAYERS)
        self.palette_tex = ctx.texture_array((palettes.SIZE, 1, len(self._fixed) + SPARE_LAYERS), 4,
                                             palettes.bake_all() + spare)
        self.palette_tex.build_mipmaps()
        self.palette_tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.palette_tex.repeat_x = True
        self.palette_tex.repeat_y = False
        self._overlay_tex = None

    def view(self) -> "View":
        return View(self)

    def layer(self, pal: palettes.Palette) -> int:
        """The palette texture layer holding ``pal``. A made-up palette is
        baked into a spare layer the first time, taking over the one drawn
        least recently once they're all used (each screen draws at most two
        palettes a frame, so a layer in use is never the oldest)."""
        if pal in self._fixed:
            return self._fixed[pal]
        if pal in self._made:
            self._made.move_to_end(pal)
            return self._made[pal]
        if len(self._made) < SPARE_LAYERS:
            layer = len(self._fixed) + len(self._made)
        else:
            _, layer = self._made.popitem(last=False)
        self.palette_tex.write(palettes.bake(pal), viewport=(0, 0, layer, palettes.SIZE, 1, 1))
        self.palette_tex.build_mipmaps()
        self._made[pal] = layer
        return layer

    def overlay(self, surface, target: moderngl.Framebuffer, origin, upload: bool = True) -> None:
        """Blend a pygame SRCALPHA surface over ``target``, its bottom-left
        corner at ``origin`` (GL pixels: y counts up from the bottom).
        ``upload=False`` reuses the pixels sent last time."""
        import pygame
        size = surface.get_size()
        if self._overlay_tex is None or self._overlay_tex.size != size:
            if self._overlay_tex is not None:
                self._overlay_tex.release()
            self._overlay_tex = self.ctx.texture(size, 4)
            self._overlay_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            upload = True
        if upload:
            self._overlay_tex.write(pygame.image.tobytes(surface, "RGBA", True))
        target.viewport = (*origin, *size)
        target.use()
        self._overlay_tex.use(0)
        _set(self.overlay_prog, "uTex", 0)
        _set(self.overlay_prog, "uOrigin", tuple(origin))
        _set(self.overlay_prog, "uSize", size)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.overlay_vao.render(vertices=3)
        self.ctx.disable(moderngl.BLEND)


class View:
    """Everything one screen-sized area needs; resized to fit as it goes."""

    def __init__(self, renderer: Renderer):
        self.r = renderer
        self.ctx = renderer.ctx
        self.size = None            # the passes' resolution
        self.screen_size = None
        self.fields = []            # current, next, blur scratch
        self.frame = self.frame_fbo = None
        self.text_tex = None
        self._text = None

    def release(self):
        for t in self.fields:
            t.release()
        self.fields = []
        for obj in (self.frame_fbo, self.frame, self.text_tex):
            if obj is not None:
                obj.release()
        self.frame = self.frame_fbo = self.text_tex = None

    def resize(self, screen_size, resolution: str = "native", text: str = "") -> None:
        size = render_size(screen_size, resolution)
        if size == self.size and tuple(screen_size) == self.screen_size:
            return
        self.release()
        self.size, self.screen_size = size, tuple(screen_size)
        self.fields = [_Target(self.ctx, size) for _ in range(3)]
        if size != self.screen_size:
            self.frame = self.ctx.texture(size, 4)
            self.frame.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.frame_fbo = self.ctx.framebuffer(color_attachments=[self.frame])
        self._text = None
        self.set_text(text)

    def set_text(self, text: str) -> None:
        """The "subliminal" text as a mask: inside the letters the palette pass
        shifts the bands by half a repeat, so the text is made of the same
        bands, out of phase, and cycles with them."""
        if text == self._text and self.text_tex is not None:
            return
        self._text = text
        import pygame                       # fonts only; no display needed
        pygame.font.init()
        w, h = self.size
        surf = pygame.Surface((w, h))
        surf.fill((0, 0, 0))
        if text:
            fit = int(h * 0.18)
            font = pygame.font.SysFont("arialblack,arial", fit, bold=True)
            width = font.size(text)[0]
            if width > w * 0.9:
                font = pygame.font.SysFont("arialblack,arial", max(4, int(fit * w * 0.9 / width)), bold=True)
            img = font.render(text, True, (255, 255, 255))
            surf.blit(img, img.get_rect(center=(w // 2, h // 2)))
        mask = pygame.image.tobytes(surf, "RGBA", True)[0::4]      # bottom row first, as GL
        if self.text_tex is not None:
            self.text_tex.release()
        self.text_tex = self.ctx.texture((w, h), 1, mask)
        self.text_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def _field(self, sc: scene.Scene, show: Show, settings: Settings, target: _Target) -> None:
        r = self.r
        p, q = scene.uniform_data(sc, show.drift_clock)
        prog = r.field_prog
        prog["uP"].write(p)
        prog["uQ"].write(q)
        _set(prog, "uRes", self.size)
        _set(prog, "uCount", min(len(sc.particles), scene.MAX_PARTICLES))
        _set(prog, "uTile", LAYOUT_INDEX[settings.layout])
        _set(prog, "uDensity", settings.band_density)
        target.fbo.use()
        r.field_vao.render(vertices=3)
        if settings.blur > 0:
            # The setting is in pixels at 1080p, so the preview box, a 4K
            # screen and the 640x480 mode all look equally blurred.
            sigma = max(0.5, min(25.0, settings.blur * self.size[1] / 1080))
            scratch = self.fields[2]
            _set(r.blur_prog, "uSigma", sigma)
            _set(r.blur_prog, "uTex", 0)
            scratch.fbo.use()
            target.tex.use(0)
            _set(r.blur_prog, "uDir", (1.0, 0.0))
            r.blur_vao.render(vertices=3)
            target.fbo.use()
            scratch.tex.use(0)
            _set(r.blur_prog, "uDir", (0.0, 1.0))
            r.blur_vao.render(vertices=3)

    def draw(self, show: Show, settings: Settings, target: moderngl.Framebuffer, origin=(0, 0)) -> None:
        """One frame of ``show`` into ``target``, covering ``screen_size`` pixels
        from ``origin`` (GL pixels: y counts up from the bottom)."""
        r = self.r
        self.set_text(settings.text)
        self._field(show.current, show, settings, self.fields[0])
        mix = show.mix
        if show.next is not None:
            self._field(show.next, show, settings, self.fields[1])

        if self.frame_fbo:
            out, out_origin = self.frame_fbo, (0, 0)
        else:
            out, out_origin = target, tuple(origin)
            target.viewport = (*out_origin, *self.size)
        out.use()
        prog = r.pal_prog
        self.fields[0].tex.use(0)
        self.fields[1 if mix > 0 else 0].tex.use(1)
        self.text_tex.use(2)
        r.palette_tex.use(3)
        for name, unit in (("uFieldA", 0), ("uFieldB", 1), ("uText", 2), ("uPal", 3)):
            _set(prog, name, unit)
        pal_a = show.current.palette
        pal_b = show.next.palette if show.next is not None else pal_a

        def shift(pal):             # half of one palette repeat
            return 0.5 / pal.repeats if settings.text else 0.0

        _set(prog, "uOrigin", out_origin)
        _set(prog, "uLayerA", float(r.layer(pal_a)))
        _set(prog, "uLayerB", float(r.layer(pal_b)))
        _set(prog, "uMix", mix)
        _set(prog, "uPhase", show.phase)
        _set(prog, "uShiftA", shift(pal_a))
        _set(prog, "uShiftB", shift(pal_b))
        _set(prog, "uClassic", 1 if settings.colours == "classic" else 0)
        _set(prog, "uBlurred", 1 if settings.blur > 0 else 0)
        r.pal_vao.render(vertices=3)

        if self.frame_fbo:
            target.viewport = (*origin, *self.screen_size)
            target.use()
            self.frame.use(0)
            _set(r.present_prog, "uFrame", 0)
            _set(r.present_prog, "uOrigin", tuple(origin))
            _set(r.present_prog, "uScreen", self.screen_size)
            r.present_vao.render(vertices=3)
