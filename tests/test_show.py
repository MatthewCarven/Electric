import random

import pytest

from electric import palettes
from electric.config import Settings
from electric.show import Show


def make(**kw):
    return Show(Settings(**kw), 16 / 9, seed=1, rng=random.Random(0))


def test_cut_when_crossfade_is_zero():
    show = make(crossfade_seconds=0)
    first = show.current
    show.new_image()
    assert show.next is None and show.current is not first and show.mix == 0


def test_crossfade_runs_then_lands():
    show = make(crossfade_seconds=2)
    first = show.current
    show.new_image()
    assert show.current is first and show.next is not None
    show.update(0.05)
    assert show.mix == pytest.approx(0.025)
    for _ in range(40):
        show.update(0.05)
    assert show.next is None and show.current is not first


def test_new_image_every_n_seconds():
    show = make(new_image_seconds=5, crossfade_seconds=0)
    seeds = {show.current.seed}
    for _ in range(int(16 / 0.05)):
        show.update(0.05)
        seeds.add(show.current.seed)
    assert len(seeds) == 4                      # the first, then at 5, 10 and 15 s


def test_never_means_never():
    show = make(new_image_seconds=0)
    first = show.current
    for _ in range(1000):
        show.update(0.1)
    assert show.current is first


def test_new_palette_each_image_always_changes_it():
    show = make(crossfade_seconds=0)
    for _ in range(50):
        before = show.current.palette
        show.new_image()
        assert show.current.palette != before


def test_fixed_palette_when_asked():
    show = make(crossfade_seconds=0, new_palette_each_image=False, palette="Greenland")
    for _ in range(5):
        show.new_image()
        assert show.current.palette.name == "Greenland"


def test_palette_change_keeps_the_particles_and_crossfades():
    show = make(crossfade_seconds=1)
    show.set_palette("Hypnotic")
    assert show.next.particles == show.current.particles and show.next.palette.name == "Hypnotic"
    assert show.settings.palette == "Hypnotic"


def test_new_palette_each_image_reaches_every_choice():
    show = make(crossfade_seconds=0)
    seen = set()
    for _ in range(400):
        show.new_image()
        seen.add(show.current.palette.choice)
    assert seen == set(palettes.NAMES)


def test_new_image_mid_fade_starts_from_the_incoming_one():
    show = make(crossfade_seconds=2)
    show.new_image()
    incoming = show.next
    show.update(0.5)
    show.new_image()
    assert show.current is incoming and show.mix == 0


def test_phase_cycles_and_pauses_and_reverses():
    show = make(cycling="fast")                 # 0.25 cycles a second
    show.update(0.1)
    assert show.phase == pytest.approx(0.025)
    show.paused = True
    show.update(0.1)
    assert show.phase == pytest.approx(0.025)
    show.paused = False
    show.settings.reverse = True
    show.update(0.1)
    assert show.phase == pytest.approx(0.0, abs=1e-12) or show.phase == pytest.approx(1.0)


def test_a_stall_is_capped():
    show = make(new_image_seconds=5, crossfade_seconds=0)
    first = show.current
    show.update(30)                             # a 30 s hitch counts as 0.1 s
    assert show.current is first and show.clock == pytest.approx(0.1)


def test_1997_gives_a_fresh_tint_each_image():
    show = make(crossfade_seconds=0, new_palette_each_image=False, palette="1997")
    tints = set()
    for _ in range(20):
        show.new_image()
        assert show.current.palette.choice == "1997"
        tints.add(show.current.palette.tint)
    assert len(tints) > 10


def test_random_makes_up_a_palette_each_image():
    show = make(crossfade_seconds=0, new_palette_each_image=False, palette="Random")
    made = set()
    for _ in range(20):
        show.new_image()
        assert show.current.palette.choice == "Random"
        made.add(show.current.palette)
    assert len(made) == 20


def test_stepping_palettes_walks_the_choices():
    last_named = palettes.NAMED[-1].name
    show = make(crossfade_seconds=0, new_palette_each_image=False, palette=last_named)
    show.step_palette(1)
    assert show.settings.palette == "1997" and show.current.palette.tint
    show.step_palette(1)
    assert show.settings.palette == "Random" and show.current.palette.choice == "Random"
    show.step_palette(1)
    assert show.settings.palette == "Default" and show.current.palette is palettes.NAMED[0]
    show.step_palette(-1)
    assert show.settings.palette == "Random"
