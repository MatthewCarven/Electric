"""The settings panel, driven by synthetic mouse and key events (no window)."""

import pygame
import pytest

from electric.config import Settings
from electric.panel import Panel
from electric.show import Show


class FakeApp:
    def __init__(self):
        self.settings = Settings(crossfade_seconds=0, new_palette_each_image=False)
        self.show = Show(self.settings, 16 / 9, seed=1)
        self.fullscreen_toggles = 0
        self.saves = 0

    def toggle_fullscreen(self):
        self.fullscreen_toggles += 1

    def save_settings(self):
        self.saves += 1
        return "C:/somewhere/config.json"


@pytest.fixture
def ui():
    app = FakeApp()
    panel = Panel(app)
    panel.window = (1600, 1200)
    return app, panel


def where(panel, key=None, label=None, at=0.75):
    """Window position over a row's control, ``at`` of the way across it."""
    x0, y0 = panel.origin()
    pad, cx, right = panel._columns()
    for row, y, h in panel._layout:
        if (key and row.key == key) or (label and label in [b[0] for b in row.buttons]):
            if row.kind == "buttons":
                i = [b[0] for b in row.buttons].index(label)
                bx, bw = panel._button_spans(row)[i]
                x = bx + bw / 2
            elif row.kind in ("slider", "number"):
                a, b = panel._slider_span()
                x = a + at * (b - a)
            elif row.kind == "toggle":
                x = pad + 4
            else:
                x = cx + at * (right - cx)
            return round(x0 + x), round(y0 + y + h / 2 - panel.scroll)
    raise KeyError(key or label)


def click(panel, pos):
    used = panel.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    panel.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
    return used


def key(panel, k, text=""):
    return panel.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=text, mod=0))


def test_choice_steps_both_ways(ui):
    app, panel = ui
    click(panel, where(panel, "cycling", at=0.9))
    assert app.settings.cycling == "fast"
    click(panel, where(panel, "cycling", at=0.1))
    click(panel, where(panel, "cycling", at=0.1))
    assert app.settings.cycling == "slow"


def test_particle_type_change_brings_a_new_image(ui):
    app, panel = ui
    seed = app.show.current.seed
    click(panel, where(panel, "particle_type", at=0.9))
    assert app.settings.particle_type == "Melons"
    assert app.show.current.seed != seed
    assert {p.type for p in app.show.current.particles} == {2}


def test_palette_choice_follows_the_picture(ui):
    app, panel = ui
    click(panel, where(panel, "palette", at=0.9))
    assert app.show.target.palette.name == "Neon" and app.settings.palette == "Neon"


def test_slider_click_and_drag(ui):
    app, panel = ui
    click(panel, where(panel, "band_density", at=0.0))
    assert app.settings.band_density == pytest.approx(0.2)
    panel.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=where(panel, "band_density", at=0.5), button=1))
    panel.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=where(panel, "band_density", at=1.0), rel=(0, 0), buttons=(1, 0, 0)))
    panel.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=where(panel, "band_density", at=1.0), button=1))
    assert app.settings.band_density == pytest.approx(4.0)


def test_number_slider_runs_from_random_to_sixteen(ui):
    app, panel = ui
    click(panel, where(panel, "particle_count", at=0.5))
    assert app.settings.random_count is False and app.settings.particle_count == 8
    assert len(app.show.current.particles) == 8
    click(panel, where(panel, "particle_count", at=0.0))
    assert app.settings.random_count is True
    assert panel._value_text(panel.rows[2]) == "random"


def test_toggle(ui):
    app, panel = ui
    click(panel, where(panel, "reverse"))
    assert app.settings.reverse is True
    click(panel, where(panel, "reverse"))
    assert app.settings.reverse is False


def test_typing_text_keeps_keys_from_the_app(ui):
    app, panel = ui
    click(panel, where(panel, "text"))
    assert key(panel, pygame.K_h, "H") and key(panel, pygame.K_i, "I")
    key(panel, pygame.K_BACKSPACE)
    assert key(panel, pygame.K_RETURN)
    assert app.settings.text == "H"
    assert not key(panel, pygame.K_n, "n")      # not focused: N goes to the app


def test_buttons(ui):
    app, panel = ui
    seed = app.show.current.seed
    click(panel, where(panel, label="New image"))
    assert app.show.current.seed != seed
    click(panel, where(panel, label="Fullscreen"))
    assert app.fullscreen_toggles == 1
    click(panel, where(panel, "reverse"))
    assert panel.unsaved
    click(panel, where(panel, label="Save settings"))
    assert app.saves == 1 and not panel.unsaved and "config.json" in panel.save_note
    click(panel, where(panel, label="Hide (H)"))
    assert not panel.visible
    assert not click(panel, where(panel, "reverse"))   # hidden: nothing reaches it


def test_wheel_steps_controls_and_scrolls_the_rest(ui, monkeypatch):
    app, panel = ui
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: where(panel, "blur"))
    panel.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert app.settings.blur == 0.5
    panel.window = (1600, 400)                  # shorter than the panel: it scrolls
    x0, y0 = panel.origin()
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (x0 + 10, y0 + 10))
    panel.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert panel.scroll > 0
    assert panel.render().get_height() == 400 - 2 * panel.margin


def test_clicks_outside_go_to_the_picture(ui):
    _, panel = ui
    assert not click(panel, (5, 5))


def test_render_fits_and_scales():
    app = FakeApp()
    for scale in (1.0, 1.5):
        panel = Panel(app, scale=scale)
        panel.window = (3840, 2160)
        surf = panel.render()
        assert surf.get_width() == round(320 * scale)
        assert surf.get_height() == panel.content_height
