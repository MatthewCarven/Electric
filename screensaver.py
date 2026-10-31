#!/usr/bin/env python3
"""Windows screensaver entry point: what ``Electric.scr`` runs.

Windows starts a ``.scr`` with one of these:

    (nothing) or /s   run: fullscreen on every monitor, ends on any input
    /p <hwnd>         animate the little preview monitor in Screen Saver Settings
    /c[:<hwnd>]       the Settings button: opens Electric with its settings
                      panel; "Save settings" there writes the config.json this
                      screensaver reads, so nothing needs rebuilding

Anything after /s is passed to the app (the smoke tests use --hidden --frames N).
A screensaver has no console, so a crash at startup is written to
``%APPDATA%\\Electric\\error.log`` instead of vanishing.
"""

import os
import sys
import traceback


def parse_mode(argv):
    """Return ('s' | 'p' | 'c', hwnd or None) from a Windows .scr command line."""
    if len(argv) < 2 or not argv[1]:
        return "s", None
    arg = argv[1].lower()
    flag = arg[:2]
    if flag == "/p":
        hwnd = argv[2] if len(argv) > 2 else (arg[3:] or None)
        return "p", hwnd
    if flag == "/c":
        return "c", None
    return "s", None


def run(argv):
    mode, hwnd = parse_mode(argv)
    from electric import app
    if mode == "c":
        return app.main([])
    if mode == "p":
        if os.name != "nt" or not hwnd:
            return 0
        settings = app.parse([])[0]
        from electric import preview
        return preview.run(int(hwnd), settings)
    return app.main(["--screensaver", *argv[2:]])


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    try:
        return run(argv)
    except SystemExit:
        raise
    except Exception:
        from electric import config
        log = config.user_config_path().parent / "error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"--- {' '.join(argv)}\n{traceback.format_exc()}\n")
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.exit(main())
