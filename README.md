# Electric

A GPU remake of *Electric !*, JX Bardant's 1997 freeware screensaver: the
electric field of particles laid at random on the screen, drawn as bands of a
256-colour palette that cycles forever.

The original computed its image once and animated it by rotating the hardware
palette, so on any True Colour screen it froze. This one does the same thing
in shaders: the field goes into a float texture, and each frame only the
palette lookup moves, so it runs at the screen's refresh rate, at any
resolution, on every monitor.

All eight of the original's particle types are here, with the potentials its
own help text describes (Electrons 1/r², Melons sin r, Dindons r, Cochons
spiral, Croûtons sin θ, Jambons Cauchy-Lorentz³, Cornichons θ, Oignons a
custom spiral), with tiling, dissymmetric tiling, blurring and the
"subliminal" text line.

## Two files

Download them from the
[Releases page](https://github.com/MatthewCarven/Electric/releases/latest), or
build them with `build.ps1` (below). Both use the same settings. They're not
signed, so the first time Windows SmartScreen may say "Windows protected your
PC": **More info**, then **Run anyway**.

**`Electric.exe`**: double-click it to run Electric in a window, with a
settings panel down the right. Everything in the panel changes the picture as
you change it. **Save settings** keeps them, and that's also what the
screensaver reads. `H` hides the panel, `F` goes fullscreen.

**`Electric.scr`**: the screensaver. Right-click it in Explorer and choose
**Install**. It covers every monitor, each with a picture of its own, and the
first key, click or real mouse movement ends it (tick "Ignore mouse moves" to
make it keys and clicks only, as the original's option did). Windows' little
preview monitor shows it running, and the **Settings** button opens the same
panel as the `.exe`.

## Palettes

**Default, Neon, Gaudy, Hypnotic, Greenland, Alien**: the original's palette
names, with colours of this remake's own.

**Inferno, Ocean, Sunset, Aurora, Candy, Toxic, Copper, Peacock, Fire and
Ice, Midnight, Thermal**: more of this remake's own.

**1997**: the original's own look, measured from the real 1997 program
running on this machine. Each image gets one random tint: a ramp from black up
to that colour with a hard edge back to black. The ramps are built exactly as
the original built them.

**Random**: a palette made up for each image, so no two look alike. It's built
from a colour harmony (neighbouring hues, opposites, triads...) in one of
four styles: colours glowing out of black, bands of each colour and its
shadow, hard stripes, or a smooth cosine wave through colour space. Ones whose
colours are all equally light get thrown away, so the bands always stand out.

With **New palette each image** ticked, every new image gets a different
palette, "1997" and "Random" included.

## Keys

| Key | |
|---|---|
| `H` | show / hide the settings panel |
| `N` | new image |
| `P` / `Shift+P` | next / previous palette |
| `T` / `Shift+T` | next / previous particle type |
| `C` | classic (256 indexed colours) or modern (smooth, anti-aliased) |
| `L` | layout: normal, tiling, dissymmetric tiling |
| `B` | blurring: off, light, heavy |
| `D` | drift: particles wander |
| `+` / `-` | band density |
| `[` / `]` | palette cycling speed |
| `R` | reverse the cycling |
| `Space` | pause the cycling |
| `F` / `F11` | fullscreen |
| `S` | screenshot into `captures/` |
| `W` | save settings (the panel's Save button) |
| `Esc` / `Q` | quit |

## Build

```bash
python -m pip install -r requirements.txt
```

```bash
pwsh -File build.ps1
```

That makes `Electric.exe` and `Electric.scr` (about 17 MB each) in this
folder; `build.ps1 app` or `build.ps1 screensaver` makes just one. The icon is
rendered fresh each build.

## Run from source

Needs Python 3.11+ and an OpenGL 3.3 GPU.

```bash
python main.py
```

```bash
python main.py --type Cochons --palette 1997 --fullscreen
```

```bash
python screensaver.py /s
```

`python main.py --help` lists every option (`Electric.exe --help` too, from
a terminal); `--list` shows the particle types and palettes. On a laptop
with two GPUs it asks for the discrete one (`--gpu high-performance`, the
default); `power-saving` asks for the integrated one, `system` leaves it to
Windows.

## Settings file

Every setting lives in `config.json`; the panel's Save button and
`--write-config` write it. The first of these that exists is read:
`--config PATH`, the `ELECTRIC_CONFIG` environment variable,
`%APPDATA%\Electric\config.json`, `config.json` beside the program. Order of
precedence: defaults, then the file, then the command line. A bad value only
resets that one setting. A crash at startup is written to
`%APPDATA%\Electric\error.log`.

## Pictures without a window

```bash
python main.py --snapshot frame.png --seed 1234 --size 1920x1080
```

```bash
python main.py --sheet palettes
```

`--sheet types` draws each particle type side by side; `--sheet palettes`
draws one scene in every palette plus the effects. Both go to `captures/`.

## The shader lab

`lab/electric-lab.html` is the same renderer in WebGL 2 with a settings
panel: open it in a browser, no install. Seeds are shared, so a seed found in
the lab gives the same image here. It has only the first six palettes and
predates the multi-monitor origin, and its shaders and `electric/shaders/`
are kept in step by hand.

## Tests

```bash
python -m pytest
```

The tests never touch your real settings. The GPU tests render offscreen and
skip themselves where no OpenGL 3.3 context can be made.

## Layout

| | |
|---|---|
| `main.py` | the app (`Electric.exe`) |
| `screensaver.py` | the screensaver (`Electric.scr`): `/s`, `/p`, `/c` |
| `electric/scene.py` | particle types, random placement, the seeded generator |
| `electric/palettes.py` | the named palettes, the 1997 ramps, Random |
| `electric/show.py` | timing: new images, crossfades, palette phase |
| `electric/renderer.py` | the GPU passes (field, blur, palette, panel overlay) |
| `electric/shaders/` | the GLSL |
| `electric/panel.py` | the settings panel |
| `electric/app.py` | command line, window, keys, both modes |
| `electric/monitors.py` | monitor layout for the screensaver |
| `electric/preview.py` | the Screen Saver Settings preview |
| `electric/snapshot.py` | offscreen frames and contact sheets |
| `electric/config.py` | settings and the config file |
| `tools/make_icon.py` | renders the icon |
| `original/` | the 1997 original (v1.3.1, JX Bardant's freeware, unchanged), for a little history |
