"""The settings panel: every option, changed on the fly with the mouse.

Drawn with pygame into a transparent surface that the renderer blends over the
picture, so it works windowed and fullscreen alike. Every change applies at
once; "Save settings" writes them to the config file, which is the one the
screensaver reads. H hides and shows it, and the keys work either way.

Controls: click a choice's left or right half (or scroll over it) to step it;
click or drag a slider (or scroll over it); click a box to tick it; click the
text box and type. Scrolling anywhere else scrolls the panel when it's taller
than the window.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Callable

from electric import config, palettes

BG = (14, 16, 22, 240)
LINE = (255, 255, 255, 34)
INK = (233, 237, 245)
MUTED = (152, 162, 182)
DIM = (96, 104, 120)
ACCENT = (120, 214, 255)
CONTROL = (34, 40, 56)
CONTROL_HOVER = (50, 58, 82)


@dataclass
class Row:
    kind: str                       # header, choice, toggle, slider, number, text, buttons
    key: str = ""
    label: str = ""
    choices: tuple = ()
    lo: float = 0.0
    hi: float = 1.0
    step: float = 1.0
    fmt: Callable | None = None     # slider value -> text
    reseed: bool = False            # a new image when it changes
    buttons: tuple = ()             # (label, action name) for a buttons row


def _seconds(v):
    return "never" if v <= 0 else f"{v:.0f} s"


def rows() -> list[Row]:
    return [
        Row("header", label="Particles"),
        Row("choice", "particle_type", "Type", tuple(config.TYPE_CHOICES), reseed=True),
        Row("number", "particle_count", "Number", lo=0, hi=16, step=1, reseed=True),
        Row("slider", "band_density", "Band density", lo=0.2, hi=4, step=0.05, fmt=lambda v: f"{v:.2f}"),
        Row("header", label="Colours"),
        Row("choice", "palette", "Palette", tuple(palettes.NAMES)),
        Row("toggle", "new_palette_each_image", "New palette each image"),
        Row("choice", "cycling", "Cycling", tuple(config.CYCLING)),
        Row("toggle", "reverse", "Reverse direction"),
        Row("header", label="Images"),
        Row("slider", "new_image_seconds", "New image after", lo=0, hi=120, step=5, fmt=_seconds),
        Row("slider", "crossfade_seconds", "Crossfade", lo=0, hi=5, step=0.25,
            fmt=lambda v: "cut" if v <= 0 else f"{v:.2f} s"),
        Row("slider", "drift", "Drift", lo=0, hi=1, step=0.05, fmt=lambda v: "off" if v <= 0 else f"{v:.2f}"),
        Row("header", label="Effects"),
        Row("choice", "layout", "Layout", config.LAYOUTS),
        Row("slider", "blur", "Blurring", lo=0, hi=16, step=0.5, fmt=lambda v: "off" if v <= 0 else f"{v:g} px"),
        Row("text", "text", "Text"),
        Row("header", label="Rendering"),
        Row("choice", "colours", "Colours", config.COLOURS),
        Row("choice", "resolution", "Resolution", config.RESOLUTIONS),
        Row("choice", "gpu", "GPU (on restart)", config.GPUS),
        Row("header", label="Screensaver"),
        Row("toggle", "ignore_mouse", "Ignore mouse moves"),
        Row("buttons", buttons=(("New image", "new_image"), ("Next palette", "next_palette"),
                                ("Fullscreen", "fullscreen"))),
        Row("buttons", buttons=(("Save settings", "save"), ("Hide (H)", "hide"))),
    ]


def _snap(v, row: Row):
    v = max(row.lo, min(row.hi, v))
    return round(round((v - row.lo) / row.step) * row.step + row.lo, 6)


class Panel:
    """``app`` provides ``settings``, ``show``, ``toggle_fullscreen()`` and
    ``save_settings()`` (which returns the path it wrote)."""

    def __init__(self, app, scale: float = 1.0):
        import pygame
        self.pg = pygame
        pygame.font.init()
        self.app = app
        self.s = max(0.75, scale)
        self.visible = True
        self.rows = rows()
        self.width = self._px(320)
        self.margin = self._px(12)
        self.font = pygame.font.SysFont("segoeui,arial", self._px(14))
        self.small = pygame.font.SysFont("segoeui,arial", self._px(12))
        self.header_font = pygame.font.SysFont("segoeui,arial", self._px(12), bold=True)
        self.title_font = pygame.font.SysFont("segoeui,arial", self._px(16), bold=True)
        self.stats: list[str] = []
        self.save_note = ""
        self.focus: Row | None = None   # the text row being typed in
        self.drag: Row | None = None    # the slider being dragged
        self.hover = None               # (row, part) under the mouse
        self.scroll = 0
        self.window = (0, 0)
        self._saved = dataclasses.asdict(app.settings)
        self._layout = self._lay_out()

    def _px(self, v):
        return max(1, round(v * self.s))

    # -------------------------------------------------------------- geometry

    def _lay_out(self):
        """(row, y, height) for every row, in panel coordinates."""
        y = self._px(44)                            # under the title
        out = []
        for row in self.rows:
            h = {"header": 26, "buttons": 34}.get(row.kind, 25)
            out.append((row, y, self._px(h)))
            y += self._px(h)
        self.content_height = y + self._px(14) + self._px(17) * 4
        return out

    @property
    def view_height(self):
        return max(self._px(100), min(self.content_height, self.window[1] - 2 * self.margin))

    def origin(self):
        """Top-left of the panel, in window coordinates."""
        return self.window[0] - self.width - self.margin, self.margin

    def contains(self, pos):
        x0, y0 = self.origin()
        return self.visible and x0 <= pos[0] < x0 + self.width and y0 <= pos[1] < y0 + self.view_height

    def _columns(self):
        pad = self._px(14)
        x0 = pad + self._px(118)
        return pad, x0, self.width - pad

    def _hit(self, pos):
        """(row, part, x within the panel) under a window position, or None."""
        if not self.contains(pos):
            return None
        x0, y0 = self.origin()
        x, y = pos[0] - x0, pos[1] - y0 + self.scroll
        pad, cx, right = self._columns()
        for row, ry, rh in self._layout:
            if ry <= y < ry + rh:
                if row.kind == "buttons":
                    for i, (bx, bw) in enumerate(self._button_spans(row)):
                        if bx <= x < bx + bw:
                            return row, i, x
                    return None
                if row.kind == "toggle":
                    return row, "box", x
                if row.kind == "header" or x < cx:
                    return None
                return row, "control", x
        return None

    def _button_spans(self, row):
        pad = self._px(14)
        gap = self._px(6)
        n = len(row.buttons)
        w = (self.width - 2 * pad - gap * (n - 1)) / n
        return [(pad + i * (w + gap), w) for i in range(n)]

    def _slider_span(self):
        pad, cx, right = self._columns()
        return cx, right - self._px(60)

    # -------------------------------------------------------------- values

    def _value_text(self, row: Row) -> str:
        st = self.app.settings
        if row.key == "palette":
            return self.app.show.target.palette.choice
        if row.kind == "number":
            return "random" if st.random_count else str(st.particle_count)
        v = getattr(st, row.key)
        if row.kind == "slider":
            return row.fmt(v)
        if row.key == "particle_type":
            return "All of them !" if v == "All" else v
        return str(v).replace("-", " ").capitalize()

    def _slider_value(self, row: Row) -> float:
        st = self.app.settings
        if row.kind == "number":
            return 0 if st.random_count else st.particle_count
        return getattr(st, row.key)

    def _set(self, row: Row, value) -> None:
        st, show = self.app.settings, self.app.show
        if row.key == "palette":
            show.set_palette(value)
            return
        if row.kind == "number":
            st.random_count = value <= 0
            if value > 0:
                st.particle_count = int(value)
        else:
            if row.kind == "slider":
                value = type(getattr(st, row.key))(value)
            setattr(st, row.key, value)
        if row.reseed:
            show.new_image()

    def _step(self, row: Row, direction: int) -> None:
        if row.kind == "choice":
            current = self._value_text(row) if row.key == "palette" else getattr(self.app.settings, row.key)
            i = row.choices.index(current) if current in row.choices else 0
            self._set(row, row.choices[(i + direction) % len(row.choices)])
        elif row.kind in ("slider", "number"):
            new = _snap(self._slider_value(row) + direction * row.step, row)
            if new != self._slider_value(row):
                self._set(row, new)

    def _drag_to(self, row: Row, x: float) -> None:
        a, b = self._slider_span()
        t = max(0.0, min(1.0, (x - a) / max(1, b - a)))
        new = _snap(row.lo + t * (row.hi - row.lo), row)
        if new != self._slider_value(row):
            self._set(row, new)

    def _action(self, name: str) -> None:
        show = self.app.show
        if name == "new_image":
            show.new_image()
        elif name == "next_palette":
            show.step_palette(1)
        elif name == "fullscreen":
            self.app.toggle_fullscreen()
        elif name == "save":
            path = self.app.save_settings()
            self._saved = dataclasses.asdict(self.app.settings)
            self.save_note = f"Saved to {config.short(path)}"
        elif name == "hide":
            self.visible = False

    @property
    def unsaved(self) -> bool:
        return dataclasses.asdict(self.app.settings) != self._saved

    # -------------------------------------------------------------- events

    def handle(self, event) -> bool:
        """Deal with one pygame event. True if the panel used it up."""
        pg = self.pg
        if not self.visible:
            return False
        if event.type == pg.KEYDOWN and self.focus is not None:
            st = self.app.settings
            if event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_ESCAPE, pg.K_TAB):
                self.focus = None
            elif event.key == pg.K_BACKSPACE:
                st.text = st.text[:-1]
            elif event.unicode and event.unicode.isprintable() and len(st.text) < 40:
                st.text += event.unicode
            return True
        if event.type == pg.MOUSEMOTION:
            if self.drag is not None:
                self._drag_to(self.drag, event.pos[0] - self.origin()[0])
                return True
            hit = self._hit(event.pos)
            self.hover = hit[:2] if hit else None
            return self.contains(event.pos)
        if event.type == pg.MOUSEBUTTONUP and event.button == 1:
            was = self.drag is not None
            self.drag = None
            return was
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._hit(event.pos)
            if hit is None:
                self.focus = None
                return self.contains(event.pos)
            row, part, x = hit
            self.focus = None
            if row.kind == "buttons":
                self._action(row.buttons[part][1])
            elif row.kind == "toggle":
                setattr(self.app.settings, row.key, not getattr(self.app.settings, row.key))
            elif row.kind == "choice":
                pad, cx, right = self._columns()
                self._step(row, -1 if x < (cx + right) / 2 else 1)
            elif row.kind in ("slider", "number"):
                self.drag = row
                self._drag_to(row, x)
            elif row.kind == "text":
                self.focus = row
            return True
        if event.type == pg.MOUSEWHEEL:
            pos = pg.mouse.get_pos()
            if not self.contains(pos):
                return False
            hit = self._hit(pos)
            if hit and hit[0].kind in ("choice", "slider", "number"):
                self._step(hit[0], 1 if event.y > 0 else -1)
            else:
                limit = max(0, self.content_height - self.view_height)
                self.scroll = max(0, min(limit, self.scroll - event.y * self._px(40)))
            return True
        return False

    # -------------------------------------------------------------- drawing

    def _text(self, surf, text, font, colour, pos, align="left"):
        img = font.render(text, True, colour)
        x, y = pos
        if align == "right":
            x -= img.get_width()
        elif align == "center":
            x -= img.get_width() // 2
        surf.blit(img, (x, y - img.get_height() // 2))

    def render(self):
        """The panel as a transparent surface, its visible part only."""
        pg = self.pg
        st = self.app.settings
        surf = pg.Surface((self.width, self.content_height), pg.SRCALPHA)
        pg.draw.rect(surf, BG, surf.get_rect(), border_radius=self._px(10))
        pg.draw.rect(surf, LINE, surf.get_rect(), width=1, border_radius=self._px(10))
        pad, cx, right = self._columns()
        self._text(surf, "Electric", self.title_font, INK, (pad, self._px(18)))
        self._text(surf, "changes apply as you make them", self.small, MUTED, (pad, self._px(34)))
        r = self._px(4)
        for row, y, h in self._layout:
            mid = y + h // 2
            hovered = self.hover is not None and self.hover[0] is row
            if row.kind == "header":
                pg.draw.line(surf, LINE, (pad, y + self._px(6)), (right, y + self._px(6)))
                self._text(surf, row.label.upper(), self.header_font, ACCENT, (pad, mid + self._px(3)))
                continue
            if row.kind == "buttons":
                for i, (bx, bw) in enumerate(self._button_spans(row)):
                    label, action = row.buttons[i]
                    if action == "save" and self.unsaved:
                        label += " *"
                    rect = pg.Rect(round(bx), y + self._px(4), round(bw), h - self._px(8))
                    hot = hovered and self.hover[1] == i
                    pg.draw.rect(surf, CONTROL_HOVER if hot else CONTROL, rect, border_radius=r)
                    pg.draw.rect(surf, ACCENT if hot else LINE, rect, width=1, border_radius=r)
                    self._text(surf, label, self.small, INK, rect.center, "center")
                continue
            if row.kind == "toggle":
                box = pg.Rect(pad, mid - self._px(7), self._px(14), self._px(14))
                pg.draw.rect(surf, CONTROL_HOVER if hovered else CONTROL, box, border_radius=self._px(3))
                pg.draw.rect(surf, ACCENT if hovered else LINE, box, width=1, border_radius=self._px(3))
                if getattr(st, row.key):
                    pg.draw.lines(surf, ACCENT, False, [(box.x + self._px(3), mid), (box.x + self._px(6), mid + self._px(3)),
                                                        (box.right - self._px(3), mid - self._px(4))], max(1, self._px(2)))
                self._text(surf, row.label, self.font, INK, (box.right + self._px(8), mid))
                continue
            self._text(surf, row.label, self.font, INK, (pad, mid))
            value = self._value_text(row)
            if row.kind == "choice":
                rect = pg.Rect(cx, y + self._px(3), right - cx, h - self._px(6))
                pg.draw.rect(surf, CONTROL_HOVER if hovered else CONTROL, rect, border_radius=r)
                a = self._px(4)
                for sx, d in ((rect.x + self._px(9), -1), (rect.right - self._px(9), 1)):
                    pg.draw.polygon(surf, ACCENT if hovered else MUTED,
                                    [(sx + d * a, mid), (sx - d * a, mid - a), (sx - d * a, mid + a)])
                self._text(surf, value, self.font, INK, rect.center, "center")
            elif row.kind in ("slider", "number"):
                a, b = self._slider_span()
                t = (self._slider_value(row) - row.lo) / (row.hi - row.lo)
                t = max(0.0, min(1.0, t))
                pg.draw.line(surf, CONTROL_HOVER, (a, mid), (b, mid), self._px(4))
                pg.draw.line(surf, ACCENT, (a, mid), (a + t * (b - a), mid), self._px(4))
                pg.draw.circle(surf, INK if hovered or self.drag is row else ACCENT,
                               (round(a + t * (b - a)), mid), self._px(7))
                self._text(surf, value, self.small, MUTED, (right, mid), "right")
            elif row.kind == "text":
                rect = pg.Rect(cx, y + self._px(3), right - cx, h - self._px(6))
                focused = self.focus is row
                pg.draw.rect(surf, CONTROL_HOVER if hovered or focused else CONTROL, rect, border_radius=r)
                if focused:
                    pg.draw.rect(surf, ACCENT, rect, width=1, border_radius=r)
                shown = st.text + ("|" if focused else "")
                self._text(surf, shown or "click to type", self.font, INK if st.text or focused else DIM,
                           (rect.x + self._px(8), mid))
        y = self._layout[-1][1] + self._layout[-1][2] + self._px(10)
        for line in self.stats + ([self.save_note] if self.save_note else []):
            self._text(surf, line, self.small, MUTED, (pad, y + self._px(8)))
            y += self._px(17)
        limit = max(0, self.content_height - self.view_height)
        self.scroll = min(self.scroll, limit)
        return surf.subsurface((0, self.scroll, self.width, self.view_height))
