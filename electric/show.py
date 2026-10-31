"""The running show: which image is up, the crossfade to the next one, the
palette's rotation. No GL here, so it can be tested on its own.

Mirrors the lab's ``begin`` / ``newImage`` / ``setPalette`` and frame timing.
"""

from __future__ import annotations

import random

from electric import palettes, scene
from electric.config import Settings


class Show:
    def __init__(self, settings: Settings, aspect: float, seed: int | None = None,
                 rng: random.Random | None = None):
        self.settings = settings
        self.aspect = aspect                # for new scenes; old ones keep their layout
        self._random = rng or random.Random()
        self.clock = 0.0                    # seconds of show time
        self.drift_clock = 0.0              # advances at the drift setting's rate
        self.phase = 0.0                    # palette rotation, in cycles (0..1)
        self.paused = False                 # stops the palette, nothing else
        self.current: scene.Scene | None = None
        self.next: scene.Scene | None = None   # being faded in
        self._fade_start = 0.0
        self._image_start = 0.0
        self.new_image(seed)

    @property
    def target(self) -> scene.Scene:
        """The scene on screen once any crossfade finishes."""
        return self.next or self.current

    @property
    def mix(self) -> float:
        """How far the crossfade has got: 0 = all current, 1 = all next."""
        if self.next is None:
            return 0.0
        return min(1.0, (self.clock - self._fade_start) / max(1e-3, self.settings.crossfade_seconds))

    def _pick_palette(self, previous: palettes.Palette | None) -> palettes.Palette:
        """The palette for the next image: the chosen one, or with "new
        palette each image" any other choice ("1997" and "Random" count as one
        each)."""
        if not self.settings.new_palette_each_image:
            return palettes.choose(self.settings.palette, self._random)
        showing = previous.choice if previous is not None else None
        name = self._random.choice([n for n in palettes.NAMES if n != showing])
        return palettes.choose(name, self._random)

    def begin(self, upcoming: scene.Scene) -> None:
        """Show ``upcoming``: at once, or by crossfade from what's showing now."""
        if self.next is not None:
            self.current, self.next = self.next, None
        if self.current is None or self.settings.crossfade_seconds <= 0:
            self.current = upcoming
        else:
            self.next = upcoming
            self._fade_start = self.clock
        self._image_start = self.clock

    def new_image(self, seed: int | None = None) -> None:
        previous = self.target.palette if self.current else None
        if seed is None:
            seed = self._random.randrange(2 ** 31)
        s = self.settings
        self.begin(scene.make_scene(seed, self._pick_palette(previous), ptype=s.type_index,
                                    count=s.particle_count, random_count=s.random_count,
                                    aspect=self.aspect))

    def set_palette(self, name: str) -> None:
        """Change palette, keeping the particles (the change crossfades too)."""
        self.settings.palette = name
        self.begin(self.target.with_palette(palettes.choose(name, self._random)))

    def step_palette(self, direction: int) -> None:
        """The next (1) or previous (-1) palette choice after the one showing."""
        names = palettes.NAMES
        i = names.index(self.target.palette.choice)
        self.set_palette(names[(i + direction) % len(names)])

    def update(self, dt: float) -> None:
        dt = min(dt, 0.1)                       # a stall doesn't skip an image
        s = self.settings
        self.clock += dt
        self.drift_clock += dt * s.drift
        if not self.paused:
            self.phase = (self.phase + dt * s.cycles_per_second) % 1.0
        if s.new_image_seconds > 0 and self.clock - self._image_start > s.new_image_seconds:
            self.new_image()
        if self.next is not None and self.mix >= 1.0:
            self.current, self.next = self.next, None
