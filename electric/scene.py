"""Particles: the original's eight potential types, laid at random.

A scene is a seed, the particles it produced and a palette (a
``palettes.Palette``; nothing here looks inside it). Generation uses the
same generator (mulberry32) and draws its random numbers in the same order as
the shader lab (``lab/electric-lab.html``), so a seed found in the lab gives
the same image here, at the same aspect ratio.

Coordinates are in screen heights, centred: y runs -0.5..0.5 and x runs
-aspect/2..aspect/2. The field shader works in the same units.
"""

from __future__ import annotations

import math
from array import array
from dataclasses import dataclass

TAU = 2 * math.pi
MAX_PARTICLES = 16

# Index 0 is "all of them": each particle then gets a random type of its own.
# The help strings are the original's, word for word.
TYPES = [
    ("All of them !", "Use all particle types."),
    ("Electrons", "Potential is the inverted square of the radius."),
    ("Melons", "Potential is the sine of the radius."),
    ("Dindons", "Potential is proportional to radius."),
    ("Cochons", "Potential is spiral."),
    ("Croûtons", "Potential is sine of angle."),
    ("Jambons", "Potential is the result of a Cauchy-Lorentz transform of order 3."),
    ("Cornichons", "Potential is proportional to angle."),
    ("Oignons", "Potential is a custom spiral."),
]

# How far and how fast particles wander when drift is on (screen heights, rad/s).
DRIFT_AMPLITUDE = 0.06
DRIFT_RATE = 0.15

_M32 = 0xFFFFFFFF


def mulberry32(seed: int):
    """A callable returning floats in [0, 1), bit-identical to the lab's ``rng``."""
    state = seed & _M32

    def imul(a, b):
        return (a * b) & _M32

    def rand():
        nonlocal state
        state = (state + 0x6D2B79F5) & _M32
        t = imul(state ^ (state >> 15), 1 | state)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & _M32) ^ t
        return (t ^ (t >> 14)) / 4294967296

    return rand


@dataclass(frozen=True)
class Particle:
    type: int           # 1..8, an index into TYPES
    x: float
    y: float
    s: float            # signed strength; exactly +-1 for the angle types
    rot: float
    fx: float           # drift: frequencies and phases
    fy: float
    px: float
    py: float
    q: tuple            # two per-type parameters (see make_particle)


@dataclass(frozen=True)
class Scene:
    seed: int
    particles: tuple
    palette: object

    def with_palette(self, palette) -> "Scene":
        return Scene(self.seed, self.particles, palette)


def make_particle(rand, ptype: int, aspect: float) -> Particle:
    """One particle of type ``ptype``, placed uniformly over the screen.

    Types whose potential follows the angle (Cochons, Cornichons, Oignons) get a
    whole number of windings and a strength of exactly +-1: atan's seam is then
    a whole palette cycle, which can't be seen.
    """
    def randint(a, b):
        return a + math.floor(rand() * (b - a + 1))

    sign = -1 if rand() < 0.5 else 1
    x = (rand() - 0.5) * aspect * 0.92
    y = (rand() - 0.5) * 0.92
    s = sign * (0.6 + 0.8 * rand())
    rot = rand() * TAU
    fx, fy = 0.4 + rand(), 0.4 + rand()
    px, py = rand() * TAU, rand() * TAU
    if ptype == 1:      # Electrons: coefficient, softening
        q = (0.012, 0.00002)
    elif ptype == 2:    # Melons: frequency, amplitude
        q = (15 + 20 * rand(), 0.15 + 0.2 * rand())
    elif ptype == 3:    # Dindons: slope
        q = (0.6 + 0.9 * rand(), 0)
    elif ptype == 4:    # Cochons: radial rate, windings
        q = (1 + 1.5 * rand(), randint(1, 3))
        s = sign
    elif ptype == 5:    # Croûtons: lobes, amplitude
        q = (randint(2, 7), 0.3 + 0.5 * rand())
    elif ptype == 6:    # Jambons: height, width
        q = (1 + 2 * rand(), 0.08 + 0.17 * rand())
    elif ptype == 7:    # Cornichons: windings
        q = (randint(1, 3), 0)
        s = sign
    elif ptype == 8:    # Oignons: log rate (either hand), windings
        q = ((0.4 + 0.8 * rand()) * (-1 if rand() < 0.5 else 1), randint(1, 4))
        s = sign
    else:
        raise ValueError(f"no particle type {ptype}")
    return Particle(ptype, x, y, s, rot, fx, fy, px, py, q)


def make_scene(seed: int, palette, *, ptype: int, count: int,
               random_count: bool, aspect: float) -> Scene:
    """Random particle placement, as the original: 1 to 5 particles when
    ``random_count``, else ``count``; one type, or a random type each when
    ``ptype`` is 0."""
    rand = mulberry32(seed)
    n = 1 + math.floor(rand() * 5) if random_count else max(1, min(MAX_PARTICLES, count))
    parts = []
    for _ in range(n):
        t = 1 + math.floor(rand() * 8) if ptype == 0 else ptype
        parts.append(make_particle(rand, t, aspect))
    return Scene(seed, tuple(parts), palette)


def uniform_data(scene: Scene, drift_clock: float) -> tuple[bytes, bytes]:
    """The field shader's ``uP`` and ``uQ`` arrays (MAX_PARTICLES vec4s each).

    uP = (x, y, signed strength, type), with drift applied; uQ = (q0, q1, 0, rot).
    """
    p = array("f", bytes(16 * MAX_PARTICLES))
    q = array("f", bytes(16 * MAX_PARTICLES))
    for i, part in enumerate(scene.particles[:MAX_PARTICLES]):
        dx = DRIFT_AMPLITUDE * math.sin(drift_clock * DRIFT_RATE * part.fx + part.px)
        dy = DRIFT_AMPLITUDE * math.sin(drift_clock * DRIFT_RATE * part.fy + part.py)
        p[4 * i:4 * i + 4] = array("f", (part.x + dx, part.y + dy, part.s, part.type))
        q[4 * i:4 * i + 4] = array("f", (part.q[0], part.q[1], 0.0, part.rot))
    return p.tobytes(), q.tobytes()
