"""The GPU passes, offscreen. Skipped where no OpenGL 3.3 context can be made."""

import dataclasses

import pytest

from electric import palettes, scene, snapshot
from electric.config import Settings

SIZE = (320, 180)


@pytest.fixture(scope="module")
def off():
    try:
        return snapshot.Offscreen()
    except Exception as exc:                    # no GL here: nothing to test
        pytest.skip(f"no OpenGL 3.3 context: {exc}")


def pixels(surf):
    import pygame
    return pygame.image.tobytes(surf, "RGB")


def colours(surf):
    data = pixels(surf)
    return {data[i:i + 3] for i in range(0, len(data), 3)}


def base(**kw):
    return dataclasses.replace(Settings(new_palette_each_image=False, random_count=False,
                                        particle_count=3), **kw)


@pytest.mark.parametrize("ptype", [name for name, _ in scene.TYPES])
def test_every_type_draws_a_pattern(off, ptype):
    img = snapshot.frame(off, base(particle_type=ptype), SIZE, seed=7)
    assert img.get_size() == SIZE
    assert len(colours(img)) > 20               # bands, not a flat fill


def test_classic_shows_only_palette_entries(off):
    img = snapshot.frame(off, base(particle_type="All", colours="classic", palette="Gaudy"), SIZE, seed=3)
    data = palettes.bake(palettes.PALETTES[2])
    entries = {data[i:i + 3] for i in range(0, len(data), 4)}
    assert colours(img) <= entries              # an 8-bit screen could show this


def test_made_up_palettes_get_layers_of_their_own(off):
    import random
    from electric.renderer import SPARE_LAYERS
    from electric.show import Show
    r = off.renderer
    s = base(particle_type="All", colours="classic", palette="Random")
    shows = [Show(s, SIZE[0] / SIZE[1], seed=9, rng=random.Random(n)) for n in range(SPARE_LAYERS + 5)]
    for show in shows:                          # more made-up palettes than spare layers
        img = off.render(show, s, SIZE)
        data = palettes.bake(show.current.palette)
        assert colours(img) <= {data[i:i + 3] for i in range(0, len(data), 4)}
    layers = {r.layer(show.current.palette) for show in shows[-SPARE_LAYERS:]}
    assert len(layers) == SPARE_LAYERS and min(layers) == len(palettes.PALETTES)
    # The fixed palettes are untouched by all that.
    gaudy = palettes.bake(palettes.NAMED[2])
    img = snapshot.frame(off, base(particle_type="All", colours="classic", palette="Gaudy"), SIZE, seed=3)
    assert colours(img) <= {gaudy[i:i + 3] for i in range(0, len(gaudy), 4)}


def test_phase_rotates_the_colours(off):
    s = base(particle_type="Melons")
    a = snapshot.frame(off, s, SIZE, seed=11, phase=0.0)
    b = snapshot.frame(off, s, SIZE, seed=11, phase=0.25)
    assert pixels(a) != pixels(b)
    c = snapshot.frame(off, s, SIZE, seed=11, phase=0.0)
    assert pixels(a) == pixels(c)               # same seed, same phase, same image


def test_tiling_mirrors_the_quadrants(off):
    import pygame
    img = snapshot.frame(off, base(particle_type="All", layout="tiling", colours="classic"), SIZE, seed=5)
    left = img.subsurface((0, 0, SIZE[0] // 2, SIZE[1]))
    right = pygame.transform.flip(img.subsurface((SIZE[0] // 2, 0, SIZE[0] // 2, SIZE[1])), True, False)
    same = sum(a == b for a, b in zip(pixels(left), pixels(right))) / len(pixels(left))
    assert same > 0.97


def test_blur_text_and_low_resolution_change_the_image(off):
    s = base(particle_type="Electrons")
    plain = pixels(snapshot.frame(off, s, SIZE, seed=2))
    for change in ({"blur": 4.0}, {"text": "ELECTRIC"}, {"resolution": "640x480"}, {"layout": "dissymmetric"}):
        assert pixels(snapshot.frame(off, dataclasses.replace(s, **change), SIZE, seed=2)) != plain, change


@pytest.mark.parametrize("resolution", ["native", "half"])
def test_views_side_by_side_draw_their_own_pictures(off, resolution):
    # The screensaver puts one view per monitor in one window, each at its origin.
    import pygame
    s = base(particle_type="All", resolution=resolution)
    shows, alone = [], []
    for seed in (21, 22):
        alone.append(pixels(snapshot.frame(off, s, SIZE, seed=seed)))
        from electric.show import Show
        shows.append(Show(s, SIZE[0] / SIZE[1], seed=seed))
    wide = off.ctx.simple_framebuffer((SIZE[0] * 2, SIZE[1]))
    views = [off.renderer.view(), off.renderer.view()]
    for i, (view, show) in enumerate(zip(views, shows)):
        view.resize(SIZE, resolution)
        view.draw(show, s, wide, origin=(i * SIZE[0], 0))
    wide.viewport = (0, 0, SIZE[0] * 2, SIZE[1])
    img = pygame.transform.flip(pygame.image.frombytes(wide.read(components=3), wide.size, "RGB"), False, True)
    for i in range(2):
        assert pixels(img.subsurface((i * SIZE[0], 0, *SIZE))) == alone[i]
    for view in views:
        view.release()
    wide.release()


def test_overlay_blends_over_the_picture(off):
    import pygame
    s = base(particle_type="Melons")
    snapshot.frame(off, s, SIZE, seed=1)             # draws into off's framebuffer
    panel = pygame.Surface((40, 30), pygame.SRCALPHA)
    panel.fill((255, 0, 0, 255))
    pygame.draw.rect(panel, (0, 0, 0, 0), (20, 0, 20, 30))   # right half see-through
    fbo = off._fbo
    before = fbo.read(viewport=(30, 10, 1, 1), components=3)
    off.renderer.overlay(panel, fbo, (0, 0))
    assert fbo.read(viewport=(5, 5, 1, 1), components=3) == b"\xff\x00\x00"
    assert fbo.read(viewport=(30, 10, 1, 1), components=3) == before


def test_low_resolution_draws_big_pixels(off):
    img = snapshot.frame(off, base(particle_type="Dindons", resolution="half"), (320, 180), seed=4)
    data = pixels(img)
    row = [data[i:i + 3] for i in range(0, 320 * 3, 3)]
    assert all(row[2 * i] == row[2 * i + 1] for i in range(160))   # each pixel doubled
