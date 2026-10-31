"""The window: command line, settings, keys and the frame loop.

    python main.py                         run in a window (F for fullscreen)
    python main.py --type Cochons --palette Neon
    python main.py --snapshot out.png      one frame, offscreen, no window
    python main.py --sheet types           contact sheet into captures/
    python main.py --write-config          save these settings for next time
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from pathlib import Path

from electric import __version__, config, gpu, palettes, scene
from electric.config import Settings

HELP = {
    "particle_type": "particle type, or All for a random type each",
    "particle_count": "number of particles (when not --random-count)",
    "random_count": "1 to 5 particles at random, as the original's Random",
    "band_density": "multiplies the field: more, thinner bands",
    "palette": "palette to start on",
    "new_palette_each_image": "pick a different palette for every new image",
    "cycling": "palette cycling speed",
    "reverse": "cycle the palette the other way",
    "new_image_seconds": "seconds before a new image (0 = never)",
    "crossfade_seconds": "crossfade between images (0 = cut, as the original)",
    "drift": "particles wander at this rate (0 = still, as the original)",
    "layout": "normal, tiling (2x2 mirrored) or dissymmetric (2x2 repeated)",
    "blur": "blurring, as a gaussian sigma in pixels (0 = off)",
    "text": "the original's 'subliminal' text line",
    "colours": "modern (smooth, anti-aliased) or classic (256 indexed colours)",
    "resolution": "native, half, or 640x480 for the 1997 look",
    "gpu": "high-performance (discrete GPU), power-saving, or system",
    "ignore_mouse": "screensaver: only keys and clicks end it, not mouse moves",
}
CHOICES = {
    "particle_type": config.TYPE_CHOICES, "palette": palettes.NAMES,
    "cycling": list(config.CYCLING), "layout": config.LAYOUTS, "colours": config.COLOURS,
    "resolution": config.RESOLUTIONS, "gpu": config.GPUS,
}
KEYS = """\
keys:  N new image   P/Shift+P palette   T/Shift+T particle type   C classic/modern
       L layout   B blur   D drift   +/- band density   [ ] cycling speed   R reverse
       Space pause cycling   F/F11 fullscreen   H settings panel   S screenshot
       W save settings   Esc/Q quit"""


def _size(text):
    try:
        w, h = (int(v) for v in text.lower().split("x"))
        if w > 0 and h > 0:
            return w, h
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, like 1280x720")


def _checked(key):
    """argparse type: parse, then validate exactly as the config file is."""
    check = config.SCHEMA[key]
    kind = type(getattr(Settings(), key))

    def convert(text):
        value = text
        if kind in (int, float):
            try:
                value = float(text)
            except ValueError:
                raise argparse.ArgumentTypeError("expected a number")
        try:
            return check(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc))
    return convert


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="electric", description="Electric: a GPU remake of the 1997 Electric ! screensaver.",
        epilog=KEYS, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"Electric {__version__}")
    p.add_argument("--config", metavar="PATH", help="settings file to read (see README)")
    for f in dataclasses.fields(Settings):
        flag = "--" + f.name.replace("_", "-")
        if f.type in ("bool", bool):
            p.add_argument(flag, action=argparse.BooleanOptionalAction, help=HELP[f.name])
        else:
            p.add_argument(flag, type=_checked(f.name), metavar=f.name.split("_")[-1].upper(),
                           help=HELP[f.name] + (f" ({', '.join(CHOICES[f.name])})"
                                                if f.name in CHOICES else ""))
    p.add_argument("--type", dest="particle_type", type=_checked("particle_type"), help=argparse.SUPPRESS)
    p.add_argument("--count", dest="particle_count", type=_checked("particle_count"), help=argparse.SUPPRESS)
    p.add_argument("--seed", type=int, help="first image's seed (the lab shows seeds too)")
    p.add_argument("--fullscreen", action="store_true", help="start fullscreen")
    p.add_argument("--size", type=_size, metavar="WxH", help="window size (default: 75%% of the screen)")
    p.add_argument("--no-panel", action="store_true", help="start with the settings panel hidden")
    p.add_argument("--screensaver", action="store_true",
                   help="fullscreen on every monitor, ending on any input (what the .scr runs)")
    p.add_argument("--snapshot", metavar="PNG", help="render one frame offscreen to PNG and exit")
    p.add_argument("--sheet", choices=("types", "palettes"), help="render a contact sheet and exit")
    p.add_argument("--out", metavar="PNG", help="where --sheet writes (default captures/<sheet>.png)")
    p.add_argument("--phase", type=float, default=0.0, help="palette phase for --snapshot (0..1)")
    p.add_argument("--write-config", nargs="?", const="", metavar="PATH",
                   help="write these settings to the config file and exit")
    p.add_argument("--list", action="store_true", help="list particle types and palettes")
    p.add_argument("--frames", type=int, help=argparse.SUPPRESS)       # smoke tests: quit after N
    p.add_argument("--hidden", action="store_true", help=argparse.SUPPRESS)
    return p


def parse(argv=None):
    """(Settings, options, config path, problems): defaults < config file < flags."""
    parser = build_parser()
    pre, _ = parser.parse_known_args(argv)
    values, path, problems = config.load(pre.config)
    parser.set_defaults(**dataclasses.asdict(dataclasses.replace(Settings(), **values)))
    opts = parser.parse_args(argv)
    settings = Settings(**{f.name: getattr(opts, f.name) for f in dataclasses.fields(Settings)})
    return settings, opts, path, problems


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------

class App:
    """Two modes. The app (``Electric.exe``): a resizable window with the
    settings panel, F for borderless fullscreen. The screensaver (``--screensaver``,
    what ``Electric.scr /s`` runs): one borderless window over every monitor,
    a picture of its own on each, ending at the first key, click or real mouse
    movement."""

    MOUSE_SLACK = 8         # pixels of mouse jitter a screensaver ignores

    def __init__(self, settings: Settings, opts, config_path):
        self.settings = settings
        self.opts = opts
        self.config_path = config_path
        self.screensaver = bool(opts.screensaver)
        gpu.choose(settings.gpu)
        gpu.dpi_aware()
        import os

        import moderngl
        import pygame
        from electric import monitors
        from electric.renderer import Renderer
        from electric.show import Show
        self.pg = pygame
        pygame.init()
        pygame.display.set_caption("Electric")
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        desktop = pygame.display.get_desktop_sizes()[0]
        if self.screensaver:
            rects = monitors.monitors() or [(0, 0, *desktop)]
            (vx, vy, vw, vh), self.areas = monitors.span(rects)
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{vx},{vy}"
            flags |= pygame.NOFRAME
            size = (vw, vh)
        else:
            self.areas = None                   # the whole window, whatever its size
            flags |= pygame.RESIZABLE
            size = opts.size or (desktop[0] * 3 // 4, desktop[1] * 3 // 4)
        if opts.hidden:
            flags |= pygame.HIDDEN
        try:
            pygame.display.set_mode(size, flags, vsync=1)
        except pygame.error:
            pygame.display.set_mode(size, flags)        # no vsync: the clock caps it
        self.window = pygame.Window.from_display_module()
        if self.screensaver and not opts.hidden:
            self.window.position = (vx, vy)
            self.window.always_on_top = True
        self.fullscreen = False
        if opts.fullscreen and not self.screensaver:
            self.toggle_fullscreen()

        self.ctx = moderngl.create_context()
        self.renderer = Renderer(self.ctx)
        count = len(self.areas) if self.areas else 1
        w, h = self.window_size()
        self.shows = [Show(settings, w / h, seed=opts.seed if i == 0 else None) for i in range(count)]
        self.views = [self.renderer.view() for _ in range(count)]
        self.gpu_name = self.ctx.info["GL_RENDERER"].split("/")[0]
        self.panel = None
        if not self.screensaver:
            from electric.panel import Panel
            self.panel = Panel(self, scale=self._dpi_scale())
            self.panel.visible = not opts.no_panel
        self._panel_surface = None
        self._panel_due = 0.0
        self._mouse_start = None
        self._update_cursor()
        print(f"Electric {__version__} on {self.ctx.info['GL_RENDERER']}")

    @property
    def show(self):
        """The (first) show: what the panel and keys act on."""
        return self.shows[0]

    def window_size(self):
        w, h = self.pg.display.get_window_size()
        return max(1, w), max(1, h)

    def _dpi_scale(self) -> float:
        try:
            import ctypes
            hwnd = self.pg.display.get_wm_info()["window"]
            return ctypes.windll.user32.GetDpiForWindow(hwnd) / 96 or 1.0
        except Exception:
            return 1.0

    def _update_cursor(self):
        panel_up = self.panel is not None and self.panel.visible
        self.pg.mouse.set_visible(not self.screensaver and (panel_up or not self.fullscreen))

    def toggle_fullscreen(self):
        """Borderless fullscreen: SDL keeps the same window, so the GL
        context and everything on the GPU survive the switch."""
        if self.fullscreen:
            self.window.set_windowed()
        else:
            self.window.set_fullscreen(desktop=True)
        self.fullscreen = not self.fullscreen
        if hasattr(self, "panel"):
            self._update_cursor()

    def save_settings(self):
        path = config.write(self.config_path or config.user_config_path(), self.settings)
        self.config_path = path
        print(f"settings written to {path}")
        return path

    # ---------------------------------------------------------------- input

    def _ends_screensaver(self, event) -> bool:
        pg = self.pg
        if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN, pg.MOUSEWHEEL):
            return True
        if event.type == pg.MOUSEMOTION and not self.settings.ignore_mouse:
            if self._mouse_start is None:
                self._mouse_start = event.pos
                return False
            dx = event.pos[0] - self._mouse_start[0]
            dy = event.pos[1] - self._mouse_start[1]
            return dx * dx + dy * dy > self.MOUSE_SLACK ** 2
        return False

    def key(self, event) -> bool:
        """Handle one key. False means quit."""
        pg, s, show = self.pg, self.settings, self.show
        k, shift = event.key, bool(event.mod & pg.KMOD_SHIFT)
        if k in (pg.K_ESCAPE, pg.K_q):
            return False
        if k == pg.K_n:
            show.new_image()
        elif k == pg.K_p:
            show.step_palette(-1 if shift else 1)
        elif k == pg.K_t:
            s.particle_type = config.TYPE_CHOICES[(s.type_index + (-1 if shift else 1)) % len(scene.TYPES)]
            show.new_image()
        elif k == pg.K_c:
            s.colours = "modern" if s.colours == "classic" else "classic"
        elif k == pg.K_l:
            s.layout = config.LAYOUTS[(config.LAYOUTS.index(s.layout) + 1) % len(config.LAYOUTS)]
        elif k == pg.K_b:
            s.blur = {0.0: 2.0, 2.0: 6.0}.get(s.blur, 0.0)
        elif k == pg.K_d:
            s.drift = 0.0 if s.drift else 0.5
        elif k in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS):
            s.band_density = min(10.0, s.band_density * 1.15)
        elif k in (pg.K_MINUS, pg.K_KP_MINUS):
            s.band_density = max(0.05, s.band_density / 1.15)
        elif k in (pg.K_LEFTBRACKET, pg.K_RIGHTBRACKET):
            speeds = list(config.CYCLING)
            i = speeds.index(s.cycling) + (1 if k == pg.K_RIGHTBRACKET else -1)
            s.cycling = speeds[max(0, min(len(speeds) - 1, i))]
        elif k == pg.K_r:
            s.reverse = not s.reverse
        elif k == pg.K_SPACE:
            show.paused = not show.paused
        elif k in (pg.K_f, pg.K_F11):
            self.toggle_fullscreen()
        elif k == pg.K_h and self.panel is not None:
            self.panel.visible = not self.panel.visible
            self._update_cursor()
        elif k == pg.K_s:
            self.screenshot()
        elif k == pg.K_w:
            if self.panel is not None:
                self.panel._action("save")
            else:
                self.save_settings()
        return True

    def screenshot(self):
        pg = self.pg
        w, h = self.window_size()
        self.ctx.screen.viewport = (0, 0, w, h)
        data = self.ctx.screen.read(viewport=(0, 0, w, h), components=3)
        img = pg.transform.flip(pg.image.frombytes(data, (w, h), "RGB"), False, True)
        name = f"electric-{self.show.target.seed}-{time.strftime('%Y%m%d-%H%M%S')}.png"
        path = config.program_dir() / "captures" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        pg.image.save(img, str(path))
        print(f"saved {path}")

    # ---------------------------------------------------------------- loop

    def _status(self, fps):
        s, sc = self.settings, self.show.target
        n = len(sc.particles)
        w, h = self.window_size()
        kind = config.TYPE_CHOICES[s.type_index]
        self.pg.display.set_caption(
            f"Electric - {kind} x{n} - {sc.palette.choice} - seed {sc.seed} - "
            f"{s.cycling}{' (paused)' if self.show.paused else ''} - {fps:.0f} fps")
        if self.panel is not None:
            self.panel.stats = [f"{w}x{h} - {fps:.0f} fps - seed {sc.seed} - {n} particle{'s' * (n > 1)}",
                                self.gpu_name,
                                f"Saves to {config.short(self.config_path or config.user_config_path())}"]

    def run(self) -> int:
        from electric import monitors
        pg = self.pg
        clock = pg.time.Clock()
        frames, fps_t, fps_n = 0, 0.0, 0
        self._status(0)
        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    return 0
                if self.screensaver:
                    if self._ends_screensaver(event):
                        return 0
                    continue
                if self.panel is not None and self.panel.handle(event):
                    self._panel_due = 0.0
                    if event.type == pg.MOUSEBUTTONDOWN:
                        self._update_cursor()
                    continue
                if event.type == pg.KEYDOWN and not self.key(event):
                    return 0
            dt = clock.tick(240) / 1000
            w, h = self.window_size()
            self.ctx.screen.viewport = (0, 0, w, h)
            self.ctx.screen.use()
            self.ctx.clear(0.0, 0.0, 0.0)
            areas = self.areas or [(0, 0, w, h)]
            for show, view, rect in zip(self.shows, self.views, areas):
                show.aspect = rect[2] / rect[3]
                show.update(dt)
                view.resize(rect[2:], self.settings.resolution, self.settings.text)
                view.draw(show, self.settings, self.ctx.screen, monitors.gl_origin(rect, h))
            if self.panel is not None and self.panel.visible:
                self._draw_panel(w, h, dt)
            pg.display.flip()
            frames += 1
            fps_t += dt
            fps_n += 1
            if fps_t >= 0.5:
                self._status(fps_n / fps_t)
                fps_t, fps_n = 0.0, 0
            if self.opts.frames and frames >= self.opts.frames:
                return 0

    def _draw_panel(self, w, h, dt):
        """Redraw the panel's pixels only when something may have changed
        (it was used, or a quarter second passed); upload only then."""
        panel = self.panel
        panel.window = (w, h)
        self._panel_due -= dt
        fresh = self._panel_surface is None or self._panel_due <= 0
        if fresh:
            self._panel_surface = panel.render()
            self._panel_due = 0.25
        x, y = panel.origin()
        surf = self._panel_surface
        self.renderer.overlay(surf, self.ctx.screen, (x, h - y - surf.get_height()), upload=fresh)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    settings, opts, path, problems = parse(argv)
    for problem in problems:
        print(f"config: {problem}", file=sys.stderr)

    if opts.list:
        print("particle types:")
        for i, (name, about) in enumerate(scene.TYPES):
            print(f"  {config.TYPE_CHOICES[i]:<11} {about}")
        print("palettes: " + ", ".join(palettes.NAMES))
        return 0

    if opts.write_config is not None:
        target = opts.write_config or path or config.user_config_path()
        print(f"settings written to {config.write(target, settings)}")
        return 0

    if opts.snapshot or opts.sheet:
        from electric import snapshot
        off = snapshot.Offscreen(settings.gpu)
        seed = opts.seed if opts.seed is not None else int(time.time()) % 2 ** 31
        if opts.sheet:
            img = snapshot.sheet(off, settings, opts.sheet, seed)
            out = opts.out or config.program_dir() / "captures" / f"{opts.sheet}.png"
        else:
            img = snapshot.frame(off, settings, opts.size or (1920, 1080), seed, opts.phase)
            out = opts.snapshot
        print(f"{snapshot.save(img, out)} (seed {seed}, {off.gpu_name})")
        return 0

    return App(settings, opts, path).run()
