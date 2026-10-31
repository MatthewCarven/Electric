"""Where the monitors are, for a screensaver window that covers all of them.

The screensaver opens one borderless window over the whole virtual desktop and
draws one view per monitor inside it. Rectangles are (x, y, width, height) in
pixels, y downwards, as Windows gives them; ``gl_origin`` turns a rectangle in
the window into GL's bottom-left origin.
"""

from __future__ import annotations

import os


def monitors() -> list[tuple[int, int, int, int]]:
    """Every monitor's rectangle in desktop coordinates, the primary first.
    Empty where it can't tell (not Windows); call after ``gpu.dpi_aware()`` so
    the numbers are real pixels."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32 = ctypes.WinDLL("user32")
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                   ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayMonitors.argtypes = (wintypes.HDC, ctypes.c_void_p, proc_type, wintypes.LPARAM)
    user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
    found = []

    def visit(hmon, _hdc, _rect, _data):
        info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            found.append((not info.dwFlags & 1, (r.left, r.top, r.right - r.left, r.bottom - r.top)))
        return True

    user32.EnumDisplayMonitors(None, None, proc_type(visit), 0)
    return [rect for _, rect in sorted(found)]


def span(rects):
    """The bounding box of ``rects`` and each rect relative to it:
    ``((x, y, w, h), [(x, y, w, h), ...])``."""
    left = min(r[0] for r in rects)
    top = min(r[1] for r in rects)
    right = max(r[0] + r[2] for r in rects)
    bottom = max(r[1] + r[3] for r in rects)
    return (left, top, right - left, bottom - top), [(x - left, y - top, w, h) for x, y, w, h in rects]


def gl_origin(rect, window_height):
    """A rectangle's bottom-left corner in GL window coordinates."""
    x, y, w, h = rect
    return x, window_height - y - h
