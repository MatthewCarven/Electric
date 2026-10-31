"""Process-wide setup that must happen before any OpenGL driver loads."""

from __future__ import annotations

import os

# On NVIDIA Optimus laptops OpenGL defaults to the integrated GPU. The driver's
# shim reads SHIM_MCCOMPAT when the first GL context is made; 0x800000001
# asks for the discrete GPU, 0x800000000 for the integrated one. Measured
# 2026-10-31: Intel UHD without it, RTX 3070 Laptop with it, even when set
# from inside the process, as long as it's before the first context.
_SHIM = {"high-performance": "0x800000001", "power-saving": "0x800000000"}


def choose(preference: str) -> None:
    """Pick the GPU: "high-performance", "power-saving" or "system" (leave it to Windows)."""
    if os.name == "nt" and preference in _SHIM:
        os.environ["SHIM_MCCOMPAT"] = _SHIM[preference]


def dpi_aware() -> None:
    """Draw at the screen's real resolution rather than Windows' scaled one."""
    if os.name != "nt":
        return
    import ctypes
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
