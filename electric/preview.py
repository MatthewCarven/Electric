"""The little monitor in Windows' Screen Saver Settings.

Windows runs ``Electric.scr /p <hwnd>`` and expects a picture inside that
window. We put a child window there, render offscreen (the preview is tiny, so
reading each frame back costs nothing) and copy the frames in with
``SetDIBitsToDevice``, until Windows destroys the window.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

WS_CHILD, WS_VISIBLE, WS_DISABLED = 0x40000000, 0x10000000, 0x08000000
WM_DESTROY, WM_PAINT, WM_ERASEBKGND, WM_QUIT = 0x0002, 0x000F, 0x0014, 0x0012
WM_PRINT, WM_PRINTCLIENT = 0x0317, 0x0318
PM_REMOVE = 1
CLASS_NAME = "ElectricPreview"

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", wintypes.HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
                ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


def _api():
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    kernel32 = ctypes.WinDLL("kernel32")
    H, U, P = wintypes.HWND, wintypes.UINT, ctypes.c_void_p
    user32.GetClientRect.argtypes = (H, ctypes.POINTER(wintypes.RECT))
    user32.IsWindow.argtypes = (H,)
    user32.DefWindowProcW.argtypes = (H, U, wintypes.WPARAM, wintypes.LPARAM)
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),)
    user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       H, wintypes.HMENU, wintypes.HINSTANCE, P)
    user32.CreateWindowExW.restype = H
    user32.PeekMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), H, U, U, U)
    user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.BeginPaint.argtypes = (H, ctypes.POINTER(PAINTSTRUCT))
    user32.BeginPaint.restype = wintypes.HDC
    user32.EndPaint.argtypes = (H, ctypes.POINTER(PAINTSTRUCT))
    user32.GetDC.argtypes = (H,)
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = (H, wintypes.HDC)
    gdi32.SetDIBitsToDevice.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.c_int, ctypes.c_int, U, U, P, P, U)
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    return user32, gdi32, kernel32


def run(parent: int, settings, fps: int = 30) -> int:
    """Animate the preview inside window ``parent`` until it goes away."""
    import pygame

    from electric import gpu, snapshot
    from electric.show import Show
    gpu.dpi_aware()
    user32, gdi32, kernel32 = _api()
    rect = wintypes.RECT()
    if not user32.GetClientRect(parent, ctypes.byref(rect)) or rect.right <= 0 or rect.bottom <= 0:
        return 0
    w, h = rect.right, rect.bottom
    bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h,   # top-down
                           biPlanes=1, biBitCount=32, biCompression=0)
    frame = {"pixels": None}

    def blit(hdc):
        if frame["pixels"] is not None:
            gdi32.SetDIBitsToDevice(hdc, 0, 0, w, h, 0, 0, 0, h, frame["pixels"], ctypes.byref(bmi), 0)

    @WNDPROC
    def proc(hwnd, msg, wparam, lparam):
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            blit(user32.BeginPaint(hwnd, ctypes.byref(ps)))
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        if msg in (WM_PRINT, WM_PRINTCLIENT):         # screenshots and PrintWindow
            blit(wintypes.HDC(wparam))
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    hinst = kernel32.GetModuleHandleW(None)
    user32.RegisterClassW(ctypes.byref(WNDCLASSW(lpfnWndProc=proc, hInstance=hinst, lpszClassName=CLASS_NAME)))
    child = user32.CreateWindowExW(0, CLASS_NAME, "Electric", WS_CHILD | WS_VISIBLE | WS_DISABLED,
                                   0, 0, w, h, parent, None, hinst, None)
    if not child:
        return 1
    off = snapshot.Offscreen(settings.gpu)
    show = Show(settings, w / h)
    msg = wintypes.MSG()
    last = time.perf_counter()
    while user32.IsWindow(child):
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            if msg.message == WM_QUIT:
                return 0
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        now = time.perf_counter()
        show.update(now - last)
        last = now
        frame["pixels"] = pygame.image.tobytes(off.render(show, settings, (w, h)), "BGRA")
        hdc = user32.GetDC(child)
        if hdc:
            blit(hdc)
            user32.ReleaseDC(child, hdc)
        time.sleep(max(0.0, 1 / fps - (time.perf_counter() - now)))
    return 0
