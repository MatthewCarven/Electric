"""Scenes and palettes match the shader lab exactly.

The reference numbers were produced by the lab itself (lab/electric-lab.html)
in the desktop app's browser pane, 2026-10-31: rng(12345), makeScene(777) with
"All of them !" and a random count at 1600x900, makeScene(2024) with three
Cochons, and a rolling hash of every baked palette.
"""

import math

import pytest

from electric import palettes, scene

JS_RNG_12345 = [0.9797282677609473, 0.3067522644996643, 0.484205421525985,
                0.817934412509203, 0.5094283693470061, 0.34747186047025025]

# type, x, y, s, rot, fx, fy, px, py, q0, q1
JS_SCENE_777_ALL = [
    [1, -0.6165996193885803, 0.12232967888936401, -0.9057334918528795, 1.580786576803195,
     1.142853485746309, 1.0186862206086515, 4.859775255843228, 4.420048728268334, 0.012, 0.00002],
    [7, 0.3055433825486236, 0.04810392047278583, -1, 3.2985534601631272,
     0.4857118517160416, 1.3216361786238848, 4.60255465338982, 6.170092997253793, 1, 0],
    [3, 0.4627648509873284, 0.07509113007225096, -1.1070869157090784, 4.58262798875854,
     0.421750966552645, 0.9441050466615707, 0.17007815369492194, 1.7255210221223645, 1.2021786828059704, 0],
    [4, -0.7158463252749708, 0.14292372789233923, -1, 4.239586972226125,
     0.8344846967142076, 0.8145268714055419, 5.922494927183196, 3.9962955340240316, 1.2085216427221894, 3],
]
JS_SCENE_2024_COCHONS = [
    [4, 0.3448102672563659, 0.13848381499759854, 1, 3.2606011680749676,
     1.065603116620332, 0.7603443542961031, 0.9976912233069464, 2.8914777631635262, 2.053323336876929, 2],
    [4, -0.03534262544578976, -0.3806304826308042, 1, 2.775224830430821,
     1.326771958824247, 0.5606078445911408, 0.027021757336084407, 3.6636712841917607, 2.4993794210022315, 3],
    [4, 0.6495026251176993, -0.4481799044366926, -1, 2.3895058970375773,
     0.9208901930600405, 0.7753108610399068, 4.62899479838513, 0.5386228004187614, 1.9724502210738137, 2],
]
JS_PALETTE_HASH = {"Default": 2767779410, "Neon": 4292935414, "Gaudy": 2173107707,
                   "Hypnotic": 2242846332, "Greenland": 3258939130, "Alien": 163261644}


def flat(sc):
    return [v for p in sc.particles
            for v in (p.type, p.x, p.y, p.s, p.rot, p.fx, p.fy, p.px, p.py, p.q[0], p.q[1])]


def rows(table):
    return [v for row in table for v in row]


def test_rng_matches_the_lab():
    rand = scene.mulberry32(12345)
    assert [rand() for _ in range(6)] == JS_RNG_12345


def test_all_of_them_scene_matches_the_lab():
    sc = scene.make_scene(777, 2, ptype=0, count=3, random_count=True, aspect=1600 / 900)
    assert flat(sc) == pytest.approx(rows(JS_SCENE_777_ALL), rel=1e-12)
    assert sc.palette == 2 and sc.seed == 777


def test_fixed_count_scene_matches_the_lab():
    sc = scene.make_scene(2024, 1, ptype=4, count=3, random_count=False, aspect=1600 / 900)
    assert flat(sc) == pytest.approx(rows(JS_SCENE_2024_COCHONS), rel=1e-12)


def test_palettes_bake_like_the_lab():
    lab = [pal for pal in palettes.NAMED if pal.name in JS_PALETTE_HASH]
    assert [pal.name for pal in lab] == [pal.name for pal in palettes.NAMED[:6]]   # the lab has six
    for pal in lab:
        h = 0
        for byte in palettes.bake(pal):
            h = (h * 31 + byte) & 0xFFFFFFFF
        assert h == JS_PALETTE_HASH[pal.name], pal.name


def test_random_count_stays_between_one_and_five():
    counts = {len(scene.make_scene(s, 0, ptype=1, count=9, random_count=True, aspect=1.5).particles)
              for s in range(300)}
    assert counts == {1, 2, 3, 4, 5}


def test_fixed_count_is_clamped():
    assert len(scene.make_scene(1, 0, ptype=1, count=40, random_count=False, aspect=1).particles) == 16
    assert len(scene.make_scene(1, 0, ptype=1, count=0, random_count=False, aspect=1).particles) == 1


def test_all_of_them_uses_every_type():
    types = {p.type for s in range(200)
             for p in scene.make_scene(s, 0, ptype=0, count=5, random_count=False, aspect=1.5).particles}
    assert types == set(range(1, 9))


def test_angle_types_have_whole_windings_and_unit_strength():
    # Otherwise atan's seam shows as a line across the screen.
    for s in range(100):
        for p in scene.make_scene(s, 0, ptype=0, count=8, random_count=False, aspect=1.5).particles:
            if p.type in (4, 8):
                assert p.q[1] == int(p.q[1]) and abs(p.s) == 1
            if p.type == 7:
                assert p.q[0] == int(p.q[0]) and abs(p.s) == 1


def test_particles_land_on_screen():
    for s in range(100):
        for p in scene.make_scene(s, 0, ptype=0, count=5, random_count=False, aspect=2.0).particles:
            assert abs(p.x) <= 2.0 / 2 and abs(p.y) <= 0.5


def test_uniform_data_is_sixteen_vec4s_with_drift():
    sc = scene.make_scene(5, 0, ptype=1, count=2, random_count=False, aspect=1.5)
    p0, q0 = scene.uniform_data(sc, 0.0)
    assert len(p0) == len(q0) == 16 * 16
    p1, _ = scene.uniform_data(sc, 10.0)
    assert p0 != p1                                    # drift moves them
    import struct
    x, y, s, t = struct.unpack_from("4f", p0, 0)
    part = sc.particles[0]
    dx = scene.DRIFT_AMPLITUDE * math.sin(part.px)
    assert x == pytest.approx(part.x + dx, abs=1e-6) and t == 1
    assert struct.unpack_from("4f", p0, 2 * 16) == (0, 0, 0, 0)   # unused slots stay empty


def test_palettes_are_cyclic():
    # Rotation wraps 255 -> 0, so the ends must meet (Gaudy's hard stripes excepted).
    assert len({pal.name for pal in palettes.NAMED}) == len(palettes.NAMED)
    for pal in palettes.NAMED:
        data = palettes.bake(pal)
        assert len(data) == 256 * 4
        if pal.name != "Gaudy":
            gap = max(abs(data[255 * 4 + j] - data[j]) for j in range(3))
            assert gap <= 40, pal.name


# Measured from the real Electric !.scr in True Colour, 2026-10-31: colours of
# its captures, put in palette order by which colours touch. (divisors, entry, colour)
MEASURED_TINTS = [
    ((1, 5, 1), 250, (250, 50, 250)),
    ((2, 5, 1), 255, (127, 51, 255)),
    ((1, 2, 3), 255, (255, 127, 85)),
    ((1, 2, 3), 71, (71, 35, 23)),
    ((6, 1, 1), 255, (42, 255, 255)),
    ((6, 1, 1), 37, (6, 37, 37)),
    ((4, 2, 2), 255, (63, 127, 127)),
]


def test_1997_ramps_match_the_original():
    assert {p.tint for p in palettes.TINTS} == {(a, b, c) for a in range(1, 7) for b in range(1, 7)
                                                for c in range(1, 7) if 1 in (a, b, c)}
    assert len(palettes.TINTS) == 91                     # each has a channel at full strength
    for divisors, index, rgb in MEASURED_TINTS:
        ramp = palettes.vintage_ramp(divisors)
        assert ramp[index] == rgb and ramp[0] == (0, 0, 0)


def test_colour_counts_match_the_captures():
    # The captures had 256 colours, or exactly 128 when no channel reached 255.
    assert len(set(palettes.vintage_ramp((4, 2, 2)))) == 128
    assert len(set(palettes.vintage_ramp((2, 5, 1)))) == 256


def test_1997_layers_show_the_ramp_twice():
    pal = next(p for p in palettes.TINTS if p.tint == (1, 2, 3))
    data, ramp = palettes.bake(pal), palettes.vintage_ramp((1, 2, 3))
    for i in (0, 37, 127, 128, 200, 255):
        assert tuple(data[i * 4:i * 4 + 3]) == ramp[i * 2 % 256]


def test_choices():
    import random
    named = [pal.name for pal in palettes.NAMED]
    assert palettes.NAMES == named + ["1997", "Random"] and len(set(palettes.NAMES)) == len(palettes.NAMES)
    assert len(named) >= 17
    assert palettes.PALETTES == palettes.NAMED + palettes.TINTS
    rand = random.Random(1)
    tints = {palettes.choose("1997", rand) for _ in range(500)}
    assert len(tints) > 80 and all(p.choice == "1997" and p.tint for p in tints)
    neon = palettes.choose("Neon", rand)
    assert neon is palettes.NAMED[1] and neon.choice == "Neon"
    made = [palettes.choose("Random", rand) for _ in range(20)]
    assert all(p.choice == "Random" and p not in palettes.PALETTES for p in made)
    assert len(set(made)) == 20                          # a new one every time


def _luma(data, i):
    r, g, b = data[i * 4:i * 4 + 3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def test_random_palettes_are_seeded_varied_and_seamless():
    assert palettes.random_palette(42) == palettes.random_palette(42)
    assert palettes.random_palette(42) != palettes.random_palette(43)
    looks = set()
    for seed in range(300):
        pal = palettes.random_palette(seed)
        data = palettes.bake(pal)
        assert len(data) == 256 * 4 and pal.repeats in (1, 2, 3)
        positions = [p for p, _ in pal.stops]
        assert positions[0] == 0 and positions == sorted(positions) and positions[-1] < 1
        lumas = [_luma(data, i) for i in range(256)]
        assert max(lumas) - min(lumas) > 60, seed        # bands you can tell apart
        # Rotation wraps 255 -> 0: that step is no bigger than one inside.
        step = [max(abs(data[(i + 1) % 256 * 4 + j] - data[i * 4 + j]) for j in range(3))
                for i in range(256)]
        assert step[255] <= max(step[:255]) + 2, seed
        looks.add(data)
    assert len(looks) == 300
