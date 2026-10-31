# Electric — todo

## Matthew's calls

- [x] ~~`git init`~~: done by Matthew; repo is MatthewCarven/Electric on
      GitHub, and he OK'd pushing whenever (2026-10-31).
- [ ] **Try it on a real screen.**
  - [x] ~~Double-click `Electric.exe`~~: "Looks great" (2026-10-31).
  - [ ] Try the new palettes and Random (P steps through them).
  - [ ] `F` in the .exe: clean switch to fullscreen and back?
  - [ ] Right-click `Electric.scr` > Install: does the preview monitor
        animate? Does Settings open the panel? Does Preview / the real
        timeout cover every monitor and end on a key or mouse move?
- [x] ~~Pick the stack~~: Python + moderngl + pygame (2026-10-31).
- [x] ~~Run the original / ground truth~~: OK'd and done for the True Colour
      look (2026-10-31); see "Open questions".

## Open questions about the original

- **The named palettes** (Neon, Gaudy, Hypnotic, Greenland, Alien) only
  appear in 256-colour mode. Under `__COMPAT_LAYER=256Color` the original
  builds them, but `DefPal` in electric.ini changed nothing and the palette
  found in its memory didn't match the screen. Disassembly (`capstone`, ~2 MB,
  not installed) would read the generator straight out of the code. Matthew
  likes the current named palettes, so this would only add more choices.
- **Effects default**: several captures were tiled. Random per image?
- **Field scale**: the original puts more bands on screen; the 1997 ramps are
  shown twice per cycle to make up for it. A capture-vs-render comparison per
  particle type would tune each type's constants.

## Next

- A HUD line in fullscreen when the panel is hidden (what changed, by key).
- Bring the lab up to date: the newer palettes, 1997 and Random, `uOrigin`,
  1080p-relative blur.
- Releases: build.ps1 then `gh release create vX.Y.Z Electric.exe
  Electric.scr` (bump `electric/__init__.py`'s version first).
- The Electron cores still show faint ring aliasing where the mip level
  steps; supersampling only the core region would clean it up.
- Per-monitor shows pick palettes independently; maybe an option to keep
  them in step.

## Done

1. Decode the original; WebGL shader lab (2026-10-31).
2. Native core in Python + moderngl (2026-10-31).
3. Settings panel, Electric.exe + Electric.scr (/s every monitor, /p, /c),
   build script, the 1997 palette from the real original (2026-10-31).
4. Eleven more named palettes and Random; on GitHub (2026-10-31).
5. Release v0.1.0 with Electric.exe and Electric.scr (2026-10-31).
