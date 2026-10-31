# Electric — worklog

A GPU remake of *Electric !* (JX Bardant, 1997, French freeware screensaver).
The original lives in `original/` (v1.3.1, `Electric !.scr` plus readmes in
seven languages). Earlier homage work: the `electric` pattern in
`Python Ascii Visualizer` (ASCII, CPU, numpy).

## 2026-10-31 — The original decoded, and a WebGL shader lab

### What the original really did (read out of `Electric !.scr`)

Static analysis only (pefile on the PE's resources and data section, no
disassembly yet). The help strings name every formula, which settles most of
what the ASCII Visualizer session had to guess.

**Particles.** "Patterns represent the electric field of particles laid on the
screen." Eight types, each a different potential function, in dialog order:

| Type | Help string in the binary |
|---|---|
| Electrons | Potential is the inverted square of the radius. |
| Melons | Potential is the sine of the radius. |
| Dindons | Potential is proportional to radius. |
| Cochons | Potential is spiral. |
| Croûtons | Potential is sine of angle. |
| Jambons | Potential is the result of a Cauchy-Lorentz transform of order 3. |
| Cornichons | Potential is proportional to angle. |
| Oignons | Potential is a custom spiral. |

Plus "All of them !" (use all types) and a number of particles, or "Random":
"The number of particles is randomly chosen between 1 and 5."

**Colours.** Palettes Default, Neon, Gaudy, Hypnotic, Greenland, Alien; cycling
speed Fast / Moderate / Slow. No palette tables are stored in the data
section, so the palettes are generated in code: their real colours need a
capture or a disassembly.

**Other.** "New image after N seconds", ignore mouse moves, DirectX display
mode change (for 256-colour palette animation on True Colour desktops), power
saving.

**Effects (v1.3).** Normal, Tiling, Dissymetric tiling, Blurring, and a line of
"subliminal" text (drawn as a GDI path turned into a clip region:
`BeginPath`/`TextOutA`/`EndPath`/`PathToRegion`/`SelectClipRgn` are imported).

**Settings file.** `electric.ini`, section `[Parameters]`, keys:
`NumberOfParticles`, `RandomNumber`, `UsedParticles`, `TimeToWait`,
`IgnoreMouse`, `DefPal`, `SpeedDiv`, `AllowDirectX`, `Width`, `Height`,
`AllowPowerSaving`, `AllowText`, `Text`, `Effects`.

**Mechanism.** Imports `CreatePalette`/`RealizePalette`/`AnimatePalette`: the
field is computed once into a 256-colour indexed image, then animated only by
rotating the hardware palette. That's why True Colour showed a still image.

### The GPU design

The modern equivalent of "indexed image + rotating palette":

1. **Field pass.** A fragment shader sums every particle's potential at each
   pixel into a float texture: the indexed image, but in float.
2. **Blur pass (optional).** A separable gaussian over (cos, sin) of the field,
   read back as a circular mean. Bands soften instead of smearing across the
   palette's wrap point, and the dense cores fade to the palette's mean colour.
3. **Palette pass.** `colour = palette(fract(field + phase))`. Advancing `phase`
   is AnimatePalette. The palette is a 256x1 texture-array layer with mipmaps,
   sampled with `textureGrad`, so where bands get denser than a pixel the
   hardware averages them (anti-aliasing for free). A "Classic" switch picks one
   of 256 entries instead, as an 8-bit screen would.

Angle-based potentials (Cochons, Cornichons, Oignons) use whole-number windings,
so atan's seam is a whole palette cycle and can't be seen; band density scales
only the radial part for the same reason.

### The lab: `lab/electric-lab.html`

One self-contained file, WebGL 2, no installs. Open it in a browser. Every
option of the original is there (types, count/random, palettes, cycling speed,
new image after N seconds, tiling, dissymmetric tiling, blurring, text), plus
what a GPU makes cheap: crossfade between images, particle drift, band density,
native resolution or a 640x480 "1997" mode. Seeded RNG, seed shown in the stats.

Checked in the desktop app's browser pane: 144 fps (vsync) at 1024x768, no
console errors. Contact sheets of all eight types, all six palettes, classic +
tiling + blur, dissymmetric tiling + text all render as expected. First tuning
pass: the Electron strength was ~5x too high (bands a few pixels wide, grey
mush); strengths and palette repeats brought down. The text was invisible at
first: half a cycle on a palette that repeats twice is one whole repeat. It
now shifts by half of one repeat.

**Guesses, not the original:** all palette colours; each type's constants
(strengths, frequencies, windings); what "Dissymetric tiling" did (the lab
repeats 2x2 tiles without mirroring); how the text was coloured.

### Not done

- Not a git repo yet (Matthew's call).
- No native app yet: the stack is Matthew's decision (see TODO).
- Nothing about the original was run or captured: static analysis only.

## 2026-10-31 (later) — Native core in Python + moderngl

Matthew picked Python + moderngl + pygame. Built the `electric` package (the
plan's session 3, the native core) the same day.

**GPU selection.** moderngl's first standalone context came up on the laptop's
Intel UHD, not the RTX 3070: Optimus defaults OpenGL to the integrated GPU.
Setting `SHIM_MCCOMPAT=0x800000001` before the first context sends it to the
NVIDIA card, and it works set from inside the process (measured both ways).
`electric/gpu.py` does that by default; `gpu: power-saving` or `system` in the
settings undo it. pygame-ce 2.5.7's window context with a 3.3 core profile
lands on the RTX too.

**What's there.** The lab's three passes ported to GLSL 3.30 almost line for
line (`electric/shaders/`), plus a nearest-neighbour present pass for the
Half and 640x480 resolutions. The particle generator is the lab's mulberry32
with the same draw order, so seeds carry between the lab and the app (proved
by a test against numbers taken from the lab in the browser pane, and by
identical palette bakes). Settings follow the ASCII Visualizer's scheme:
defaults < config.json < command line, the same lookup order, never raises.
Window with keys for everything (N P T C L B D + - [ ] R Space F S W Esc),
fps and seed in the title, `--snapshot` / `--sheet` for offscreen pictures.

**Checked.** 43 tests, 1.1 s, a third of them rendering on the GPU offscreen
(every type draws, classic mode only ever shows palette entries, phase
rotates, tiling mirrors, low resolution draws doubled pixels, blur/text/
layout each change the image). A conftest points every config lookup at a
temp folder, so a test run can't touch real settings. Mutation check: 8 of 8
deliberate bugs caught (palette repeat, stall cap, accent folding, draw order,
layout mapping, present filter, classic branch, config precedence). Contact
sheets rendered offscreen match the lab's. The real window loop ran 180
frames in a hidden window (640x480 + blur + text + crossfade every second),
exit 0. Both contact sheets (16 frames at 480x270) took 0.43 s.

**Not checked: how it feels on a real screen.** Every window run so far was
hidden; fullscreen toggling (`F`, pygame's `toggle_fullscreen` on a GL
window), vsync, and the fps at full resolution are Matthew's to see.

## 2026-10-31 (evening) — Electric.exe and Electric.scr, the settings panel, the 1997 palette

Matthew: likes the palettes, wants options; both an .exe (double-click and
run) and a .scr; "more for options control on the .exe ... just to be able to
change on the fly"; ground truth welcome but optional.

**Settings panel** (`electric/panel.py`). Every setting as a row (choices
step by clicking either half or scrolling, sliders drag, ticks toggle, the
text box types), drawn with pygame into a transparent surface that the
renderer blends over the picture, so it works fullscreen too. Changes apply
at once; Save settings writes config.json, the file the .scr reads, so the
.exe doubles as the screensaver's settings editor. Redrawn and re-uploaded
only when used or every quarter second. Scales with the window's DPI and
scrolls when taller than the window. New setting `ignore_mouse` (the
original's "Ignore mouse moves").

**Renderer split** into `Renderer` (shaders, palettes, overlay) and `View`
(one screen's textures, drawn at an origin), so one window can hold a view
per monitor. Blur is now measured in pixels at 1080p, so the preview box,
4K and 640x480 look alike.

**Screensaver** (`screensaver.py`): `/s` opens one borderless always-on-top
window over the whole virtual desktop with a view and a show per monitor,
ending on key, click, wheel, or mouse movement over 8 px. `/p` renders
offscreen and copies frames into a child window of the preview HWND
(`electric/preview.py`, which also answers WM_PRINT so captures work). `/c`
opens the app with its panel. Crashes go to `%APPDATA%\Electric\error.log`.
The .exe borrows its parent terminal's console (the ASCII Visualizer's
code), and logs and says where on a crash. Fullscreen in the app is SDL's
borderless desktop fullscreen through `pygame.Window`, which keeps the GL
context.

**Build** (`build.ps1`): PyInstaller one-file, windowed, shaders collected as
data, glcontext as a hidden import, numpy and tkinter excluded. 16.7 MB each,
about 9 s per build. Icon rendered by `tools/make_icon.py` (PNG-in-ICO,
written by pygame, so no Pillow needed).

**Ground truth, run for real.** Matthew OK'd it, so the 1997 .scr ran in a
harness that plays the Screen Saver Settings dialog: an off-screen host
window, `Electric !.scr /p <hwnd>`, PrintWindow (flag 0) on its child, then
the host destroyed (the original exits cleanly). Findings:
- On a True Colour screen it shows one random tint per image: a ramp from
  black to that colour with a hard wrap. Entry i is (i//a, i//b, i//c) with
  a, b, c from 1 to 6. Integer division explains the captures exactly: a
  ramp topping out at 127 has 128 colours, others 256; every captured value
  checked (tests pin seven of them).
- The named palettes (Neon, Gaudy, ...) only exist in 256-colour mode. Under
  `__COMPAT_LAYER=256Color` it does build an 8-bit DIB and a PC_RESERVED
  palette (found in its memory), but `DefPal` in a VirtualStore electric.ini
  changed nothing and the heap palette didn't match the screen, so the named
  palettes weren't recovered. Time-boxed; disassembly would settle it.
- Several captures are tiled, so the effects default to random or tiling.
- The ini I wrote was removed after each batch; nothing left behind.

**"1997" palette**: the measured ramps, as a seventh choice; each image picks
a tint. Only the 91 tints with a full-strength channel (7 of 9 captures had
one; the dim ones look muddy). Shown twice per palette cycle, since the
original put more cycles on screen than this remake. Bright, hard-edged,
and side by side with the captures it reads as the same program.

**Checked.** 66 tests (panel driven by synthetic events, two views side by
side matching single renders, overlay blending, the 1997 ramps against the
captures, command-line parsing, monitor maths). Built files smoke-tested
with settings pointed at a scratch folder: `Electric.exe --snapshot`,
`Electric.exe` hidden for 150 frames, `Electric.scr /s` hidden, and
`Electric.scr /p` in the harness (draws, exits 0.4 s after its window goes).

**Not checked: anything on a real screen.** The visible window, the panel
under a real mouse, fullscreen switching, the .scr across real monitors,
and the .scr installed in Windows' Screen Saver Settings are Matthew's to try.

## 2026-10-31 (late) — More palettes, Random, and onto GitHub

Matthew tried Electric.exe ("Looks great"), made the GitHub repo
(MatthewCarven/Electric, "old one included for the purposes of keeping a
little history"), OK'd pushing whenever, and asked for more palettes, "maybe
a random one too".

**Eleven more named palettes**, this remake's own: Inferno, Ocean, Sunset,
Aurora, Candy, Toxic, Copper, Peacock, Fire and Ice, Midnight (thin bright
contour lines on navy), Thermal (a thermal camera's ramp with a hard wrap).
After the original six, before "1997". Candy's first colours were too pale
beside the rest on the contact sheet and got more saturation.

**Random**: a palette made up for each image (`palettes.random_palette`,
seeded, so a seed always gives the same one). Hues from a harmony
(analogous, complementary, split, triadic, square, two pairs) in one of four
styles: glow (out of black, half the time through a white flash), shadows
(each colour then a quarter-bright copy), stripes (hard edges, sometimes a
dark stripe), waves (a cosine palette, a + b cos 2pi(ct + d) with whole c, so
it wraps). Anything whose stops span less than 0.35 in luma is rerolled:
about one in ten, mostly stripes and waves whose colours were equally light
(measured over 3,000 seeds; never more than three rerolls).

**How the renderer holds them.** A scene now carries its `Palette`, not a
texture layer number. The renderer keeps the fixed palettes in their layers
and gives made-up ones 32 spare layers, baked on first use and reused least
recently drawn first. A screen draws two palettes a frame at most, so a layer
in use is never the one taken. `palettes.choose(name, rand)` replaced
`layer_for`, and `Palette.choice` replaced `name_of`.

**Checked.** 70 tests: every Random palette over 300 seeds has contrast, no
seam at the wrap (its 255 -> 0 step is no bigger than its biggest inside
step), and a look of its own; 37 made-up palettes in a row each draw only
their own colours in classic mode, and Gaudy is untouched afterwards; with
New palette each image ticked, every one of the 19 choices comes up. Contact
sheets of every palette and of 16 Random ones look right. Rebuilt; the built
exe and scr pass the smoke runs, including Random with a new image every
0.3 s in both. No error.log.

**Git.** Matthew ran `git init`. `.gitignore` now lets `original/` in (the
1997 files, unchanged), and `.gitattributes` keeps them byte for byte. The
built .exe/.scr stay out (17 MB each): GitHub Releases would be the place.

**Release v0.1.0** (Matthew: "Yes, make a release"): Electric.exe and
Electric.scr from the 11:08 build, which is newer than every source file, so
it matches the pushed code. Attached with `gh release create`, notes listing
the SHA-256 of each. The README now points at the Releases page and says what
to do about SmartScreen (the files aren't signed).
