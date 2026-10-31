"""Settings: defaults < config.json < command line.

The same scheme as the ASCII Visualizer, because the same constraint applies:
Windows can't pass options to a ``.scr``, so the screensaver reads a JSON file.
Keys are the command-line options with dashes turned into underscores
(``--new-image-seconds`` is ``"new_image_seconds"``); keys starting with ``_``
are ignored, which gives the file comments.

Search order, first file that exists wins:

1. ``--config PATH``
2. the ``ELECTRIC_CONFIG`` environment variable
3. ``%APPDATA%\\Electric\\config.json`` (``~/.config/electric/config.json`` elsewhere)
4. ``config.json`` beside the program (the ``.exe``/``.scr`` when frozen)

**Nothing here raises.** A screensaver has no console, so a bad file must not
stop it from appearing: a missing or broken file means defaults, and a bad
value means that one key keeps its default. Problems come back as messages.
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from electric import palettes, scene

CONFIG_NAME = "config.json"
CONFIG_ENV = "ELECTRIC_CONFIG"

CYCLING = {"off": 0.0, "slow": 0.04, "moderate": 0.10, "fast": 0.25}    # palette cycles per second
LAYOUTS = ("normal", "tiling", "dissymmetric")
COLOURS = ("modern", "classic")
RESOLUTIONS = ("native", "half", "640x480")
GPUS = ("high-performance", "power-saving", "system")


@dataclass
class Settings:
    particle_type: str = "Electrons"        # a TYPES name, or "All"
    particle_count: int = 3
    random_count: bool = True               # 1 to 5 particles, as the original's "Random"
    band_density: float = 1.0
    palette: str = "Default"
    new_palette_each_image: bool = True
    cycling: str = "moderate"
    reverse: bool = False
    new_image_seconds: float = 30.0         # 0 = never
    crossfade_seconds: float = 2.0          # 0 = cut, as the original
    drift: float = 0.0                      # 0 = still particles, as the original
    layout: str = "normal"
    blur: float = 0.0                       # gaussian sigma, in pixels
    text: str = ""
    colours: str = "modern"
    resolution: str = "native"
    gpu: str = "high-performance"
    ignore_mouse: bool = False              # screensaver: only keys and clicks end it, as the original's option

    # Resolved forms for the renderer.
    @property
    def type_index(self) -> int:
        return _TYPE_INDEX[_fold(self.particle_type)]

    @property
    def cycles_per_second(self) -> float:
        return CYCLING[self.cycling] * (-1 if self.reverse else 1)


def _fold(name: str) -> str:
    """Case- and accent-blind: "croutons" finds Croûtons."""
    decomposed = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().lower()


_TYPE_INDEX = {_fold(name): i for i, (name, _) in enumerate(scene.TYPES)}
_TYPE_INDEX["all"] = 0
TYPE_CHOICES = ["All"] + [name for name, _ in scene.TYPES[1:]]


# --------------------------------------------------------------------------
# Validation: each check returns the clean value or raises ValueError
# --------------------------------------------------------------------------

def _boolean(v):
    if isinstance(v, bool):
        return v
    raise ValueError("expected true or false")


def _number(lo, hi, integer=False):
    def check(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("expected a number")
        if integer and v != int(v):
            raise ValueError("expected a whole number")
        if not lo <= v <= hi:
            raise ValueError(f"expected {lo} to {hi}")
        return int(v) if integer else float(v)
    return check


def _one_of(choices, canonical=None):
    lookup = {_fold(c): c for c in choices}
    if canonical:
        lookup.update(canonical)

    def check(v):
        if isinstance(v, str) and _fold(v) in lookup:
            return lookup[_fold(v)]
        raise ValueError("expected one of " + ", ".join(choices))
    return check


def _text(v):
    if isinstance(v, str) and len(v) <= 60:
        return v
    raise ValueError("expected text of up to 60 characters")


SCHEMA = {
    "particle_type": _one_of(TYPE_CHOICES, {_fold(scene.TYPES[0][0]): "All"}),
    "particle_count": _number(1, scene.MAX_PARTICLES, integer=True),
    "random_count": _boolean,
    "band_density": _number(0.05, 10),
    "palette": _one_of(palettes.NAMES),
    "new_palette_each_image": _boolean,
    "cycling": _one_of(list(CYCLING)),
    "reverse": _boolean,
    "new_image_seconds": _number(0, 86400),
    "crossfade_seconds": _number(0, 30),
    "drift": _number(0, 5),
    "layout": _one_of(LAYOUTS),
    "blur": _number(0, 16),
    "text": _text,
    "colours": _one_of(COLOURS),
    "resolution": _one_of(RESOLUTIONS),
    "gpu": _one_of(GPUS),
    "ignore_mouse": _boolean,
}
assert set(SCHEMA) == {f.name for f in fields(Settings)}


def validate(raw: dict) -> tuple[dict, list[str]]:
    """Split a raw dict into (clean values, problem messages)."""
    clean, problems = {}, []
    if not isinstance(raw, dict):
        return clean, ["the file isn't a JSON object { ... }"]
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        check = SCHEMA.get(key)
        if check is None:
            problems.append(f"unknown setting {key!r} (ignored)")
            continue
        try:
            clean[key] = check(value)
        except ValueError as exc:
            problems.append(f"{key}: {exc}; got {value!r}, using the default")
    return clean, problems


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def program_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_config_path() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Electric" / CONFIG_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "electric" / CONFIG_NAME


def search_paths(explicit=None) -> list[Path]:
    paths = []
    if explicit:
        paths.append(Path(explicit))
    if os.environ.get(CONFIG_ENV):
        paths.append(Path(os.environ[CONFIG_ENV]))
    paths += [user_config_path(), program_dir() / CONFIG_NAME]
    return paths


def find(explicit=None):
    for path in search_paths(explicit):
        if path.is_file():
            return path
    return None


def load(explicit=None) -> tuple[dict, Path | None, list[str]]:
    """Return ``(clean values, path or None, problems)``. Never raises."""
    path = find(explicit)
    if path is None:
        problems = [f"no config file at {explicit}"] if explicit else []
        return {}, None, problems
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {}, path, [f"couldn't read {path}: {exc}; using the defaults"]
    clean, problems = validate(raw)
    return clean, path, [f"{path.name}: {p}" for p in problems]


def short(path) -> str:
    """A path with the home folder written as ~, for showing on screen."""
    path, home = Path(path), Path.home()
    try:
        return str(Path("~") / path.relative_to(home))
    except ValueError:
        return str(path)


def dump(settings: Settings) -> str:
    """JSON for a config file holding every setting at its current value."""
    body = {"_about": "Electric settings. Delete a line to get its default back; "
                      "keys starting with _ are ignored."}
    body.update(asdict(settings))
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def write(path, settings: Settings) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(settings), encoding="utf-8", newline="\n")
    return path
