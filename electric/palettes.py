"""The palettes, baked to 256 entries each.

Three kinds:

* **Named gradients.** The first six (Default, Neon, Gaudy, Hypnotic,
  Greenland, Alien) carry the original's names; the colours, and the rest of
  the list, are this remake's own. Each is one cyclic gradient repeated
  ``repeats`` times across the 256 entries, so rotating it never shows a seam.
  Baking matches the shader lab's ``bakePalette`` (the lab has the six).
* **"1997"**: the original's own look on a True Colour screen, measured from
  the real ``Electric !.scr`` running here (2026-10-31): a straight ramp from
  black up to one colour, then a hard wrap back to black. Entry ``i`` is
  ``(i // a, i // b, i // c)`` for whole numbers a, b, c from 1 to 6. Choosing
  "1997" picks one of these at random for each image, as the original did.
  (Integer division is why a ramp whose brightest channel is 127 has exactly
  128 colours, as the captures do.)
* **"Random"**: a palette made up for each image (``random_palette``), from a
  colour harmony or a cosine curve, so no two images look alike.

``PALETTES`` is every fixed layer of the palette texture (the named ones, then
the tints; the renderer uploads made-up ones as they come). ``NAMES`` is what
you choose from (the named ones, then "1997" and "Random").
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass

SIZE = 256
TINT_DIVISORS = range(1, 7)
VINTAGE = "1997"
RANDOM = "Random"


@dataclass(frozen=True)
class Palette:
    name: str
    repeats: int
    stops: tuple = ()           # (position 0..1, "#rrggbb"), first stop at 0; wraps to the first
    tint: tuple | None = None   # a 1997 ramp: its divisors (a, b, c)
    family: str = ""            # the choice it's one of ("1997", "Random"), if not its own name

    @property
    def choice(self) -> str:
        """The name you pick to get this palette."""
        return self.family or self.name


NAMED = [
    Palette("Default", 1, ((0, "#ff2020"), (1 / 6, "#ffe020"), (2 / 6, "#20e040"),
                           (3 / 6, "#20e0ff"), (4 / 6, "#2040ff"), (5 / 6, "#e020ff"))),
    Palette("Neon", 2, ((0, "#000000"), (0.30, "#1a0066"), (0.50, "#00e5ff"),
                        (0.58, "#ffffff"), (0.68, "#ff2bd6"), (0.85, "#2a0040"))),
    Palette("Gaudy", 3, ((0, "#ff1e1e"), (0.16, "#ff1e1e"), (0.20, "#ffe600"), (0.36, "#ffe600"),
                         (0.40, "#1ec81e"), (0.56, "#1ec81e"), (0.60, "#1e5aff"), (0.76, "#1e5aff"),
                         (0.80, "#ff1ee6"), (0.96, "#ff1ee6"))),
    Palette("Hypnotic", 4, ((0, "#000000"), (0.5, "#ffffff"))),
    Palette("Greenland", 2, ((0, "#03221c"), (0.25, "#0d6b3d"), (0.50, "#7fdc8c"),
                             (0.62, "#f2fff6"), (0.78, "#8fd8ff"), (0.90, "#145a7a"))),
    Palette("Alien", 2, ((0, "#050008"), (0.30, "#3d0a5c"), (0.50, "#a020f0"),
                         (0.60, "#39ff14"), (0.70, "#e6ff70"), (0.85, "#0b3d12"))),
    # This remake's own, 2026-10-31.
    Palette("Inferno", 2, ((0, "#000000"), (0.25, "#5c0a12"), (0.45, "#d42a0a"),
                           (0.62, "#ff9a1a"), (0.74, "#fff0a0"), (0.88, "#802008"))),
    Palette("Ocean", 2, ((0, "#000814"), (0.30, "#003566"), (0.50, "#0096c7"),
                         (0.62, "#90e0ef"), (0.70, "#ffffff"), (0.85, "#023e8a"))),
    Palette("Sunset", 2, ((0, "#1a0533"), (0.25, "#6b1d5c"), (0.45, "#e2445c"),
                          (0.60, "#ff8c42"), (0.72, "#ffd56b"), (0.86, "#5a2a6e"))),
    Palette("Aurora", 2, ((0, "#020814"), (0.25, "#0b3d4f"), (0.42, "#1affa0"),
                          (0.55, "#7dff6a"), (0.68, "#b46bff"), (0.84, "#1a1047"))),
    Palette("Candy", 3, ((0, "#ff4fa3"), (0.25, "#ffd84f"), (0.50, "#3fd8a8"), (0.75, "#6f78ff"))),
    Palette("Toxic", 3, ((0, "#000000"), (0.40, "#1f3d00"), (0.60, "#b6ff00"),
                         (0.70, "#f4ff9e"), (0.85, "#2b5400"))),
    Palette("Copper", 2, ((0, "#1b0f0a"), (0.30, "#8a4a24"), (0.48, "#e8a060"),
                          (0.58, "#fff2d8"), (0.70, "#4fb3a0"), (0.86, "#14453d"))),
    Palette("Peacock", 2, ((0, "#001a1a"), (0.25, "#006d6f"), (0.42, "#00b4a0"),
                           (0.55, "#d4af37"), (0.65, "#2f6fdf"), (0.82, "#3b0a6b"))),
    Palette("Fire and Ice", 1, ((0, "#000000"), (0.18, "#7a0000"), (0.30, "#ff5a00"), (0.40, "#ffe28a"),
                                (0.50, "#000000"), (0.68, "#003c8f"), (0.80, "#38c8ff"), (0.90, "#e8fbff"))),
    Palette("Midnight", 3, ((0, "#000004"), (0.40, "#0a1440"), (0.47, "#3060ff"),
                            (0.50, "#f0f4ff"), (0.53, "#3060ff"), (0.60, "#0a1440"))),
    Palette("Thermal", 1, ((0, "#000000"), (0.18, "#1a0a8c"), (0.38, "#a0108c"), (0.56, "#ff3010"),
                           (0.74, "#ffb000"), (0.90, "#ffff80"), (0.97, "#ffffff"))),
]

# Only tints with a channel at full strength: 7 of the 9 True Colour captures
# had one, and the dim ones look muddy on a modern screen. (The original did
# show a dim one now and then.)
TINTS = [Palette(f"{VINTAGE} {a}{b}{c}", 2, tint=(a, b, c), family=VINTAGE)
         for a in TINT_DIVISORS for b in TINT_DIVISORS for c in TINT_DIVISORS if 1 in (a, b, c)]

PALETTES = NAMED + TINTS
NAMES = [p.name for p in NAMED] + [VINTAGE, RANDOM]
_BY_NAME = {p.name: p for p in NAMED}


def choose(name: str, rand: random.Random) -> Palette:
    """The palette for a choice: "1997" is a random tint and "Random" a newly
    made-up palette, both drawn from ``rand``."""
    if name == VINTAGE:
        return rand.choice(TINTS)
    if name == RANDOM:
        return random_palette(rand.randrange(2 ** 31))
    return _BY_NAME[name]


# Hue offsets, in turns of the colour wheel.
_HARMONIES = (
    (0, 0.07, 0.14),                # analogous
    (0, 0.5),                       # complementary
    (0, 0.42, 0.58),                # split complementary
    (0, 1 / 3, 2 / 3),              # triadic
    (0, 0.25, 0.5, 0.75),           # square
    (0, 0.08, 0.5, 0.58),           # two neighbouring pairs
)


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, v)) * 255):02x}" for v in rgb)


def _spread(rand: random.Random, colours, weights=None, hold: float = 0.0) -> tuple:
    """Stops for ``colours`` round the cycle, each given a share of it by
    ``weights`` (random if none). ``hold`` keeps each colour flat for that part
    of its share before it blends into the next: near 1 gives hard stripes."""
    weights = weights or [rand.uniform(0.6, 1.4) for _ in colours]
    total, p, stops = sum(weights), 0.0, []
    for colour, w in zip(colours, weights):
        stops.append((p, _hex(colour)))
        if hold:
            stops.append((p + hold * w / total, _hex(colour)))
        p += w / total
    return tuple(stops)


def _contrast(pal: Palette) -> float:
    """Lightest stop minus darkest, in luma from 0 to 1."""
    lumas = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in (_rgb(c) for _, c in pal.stops)]
    return (max(lumas) - min(lumas)) / 255


def random_palette(seed: int) -> Palette:
    """A palette made up from ``seed``, in one of four styles: colours rising
    out of black (sometimes to a white flash), bands of each colour and its
    shadow, hard stripes, or a cosine curve through colour space. Every style
    wraps round to its start, so the palette rotates without a seam. One whose
    colours are all about as light as each other is thrown away for another:
    its bands would be hard to tell apart."""
    rand = random.Random(seed)
    while True:
        pal = _invent(rand, f"{RANDOM} {seed}")
        if _contrast(pal) >= 0.35:
            return pal


def _invent(rand: random.Random, name: str) -> Palette:
    style = rand.choice(("glow", "glow", "shadows", "stripes", "waves"))
    repeats = rand.choice((1, 2, 2, 3))
    if style == "waves":
        # a + b cos 2pi(c t + d), a whole number of turns per channel.
        a = [rand.uniform(0.35, 0.65) for _ in range(3)]
        b = [rand.uniform(0.3, 0.5) for _ in range(3)]
        c = [rand.choice((1, 1, 2)) for _ in range(3)]
        d = [rand.random() for _ in range(3)]
        n = 24
        stops = tuple((k / n, _hex([a[j] + b[j] * math.cos(2 * math.pi * (c[j] * k / n + d[j]))
                                    for j in range(3)])) for k in range(n))
        return Palette(name, repeats, stops, family=RANDOM)

    base = rand.random()
    hues = [(base + offset + rand.uniform(-0.03, 0.03)) % 1 for offset in rand.choice(_HARMONIES)]
    colours = [colorsys.hsv_to_rgb(h, rand.uniform(0.6, 1.0), rand.uniform(0.8, 1.0)) for h in hues]
    dark = colorsys.hsv_to_rgb(hues[0], 0.8, rand.uniform(0.0, 0.12))
    if style == "glow":
        if rand.random() < 0.5:
            colours.insert(rand.randrange(1, len(colours) + 1), (1.0, 1.0, 1.0))
        weights = [rand.uniform(1.5, 2.5)] + [rand.uniform(0.6, 1.4) for _ in colours]
        stops = _spread(rand, [dark] + colours, weights)
    elif style == "shadows":
        shadowed = []
        for r, g, b in colours:
            shadowed += [(r, g, b), (r * 0.25, g * 0.25, b * 0.25)]
        stops = _spread(rand, shadowed)
    else:                                   # stripes
        if rand.random() < 0.5:
            colours.append(dark)
        stops = _spread(rand, colours, hold=rand.uniform(0.7, 0.9))
    return Palette(name, repeats, stops, family=RANDOM)


def _rgb(h: str):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def vintage_ramp(divisors) -> list[tuple]:
    """The original's 256-entry palette for one tint, exactly as it built it."""
    return [tuple(i // d for d in divisors) for i in range(SIZE)]


def bake(pal: Palette) -> bytes:
    """256 RGBA entries."""
    out = bytearray(SIZE * 4)
    if pal.tint is not None:
        # The original's ramp, ``repeats`` times over: it mapped its field to
        # more palette cycles per screen than this remake does, so this
        # brings the bands about as close together as in its captures.
        ramp = vintage_ramp(pal.tint)
        for i in range(SIZE):
            out[i * 4:i * 4 + 4] = bytes(ramp[i * pal.repeats % SIZE] + (255,))
        return bytes(out)
    stops = [(p, _rgb(c)) for p, c in pal.stops]
    for i in range(SIZE):
        t = (i / SIZE * pal.repeats) % 1
        k = len(stops) - 1
        while k > 0 and stops[k][0] > t:
            k -= 1
        p0, c0 = stops[k]
        p1, c1 = stops[(k + 1) % len(stops)]
        if k + 1 == len(stops):
            p1 = 1
        f = (t - p0) / (p1 - p0) if p1 > p0 else 0
        for j in range(3):
            out[i * 4 + j] = math.floor(c0[j] + (c1[j] - c0[j]) * f + 0.5)   # JS Math.round
        out[i * 4 + 3] = 255
    return bytes(out)


def bake_all() -> bytes:
    """Every layer, one after another: the palette texture array's contents."""
    return b"".join(bake(p) for p in PALETTES)
