#!/usr/bin/env python3
"""Run Electric: ``python main.py`` from source, or ``Electric.exe`` once built
(``build.ps1``). Both take the same options; ``--help`` lists them."""

import os
import sys
import traceback


def _parent_pid(pid):
    """The id of the process that started ``pid`` (Windows), or None."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):              # PROCESSENTRY32W
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)    # TH32CS_SNAPPROCESS
    if snap in (None, wintypes.HANDLE(-1).value):
        return None
    try:
        entry = Entry(dwSize=ctypes.sizeof(Entry))
        found = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while found:
            if entry.th32ProcessID == pid:
                return entry.th32ParentProcessID
            found = kernel32.Process32NextW(snap, ctypes.byref(entry))
        return None
    finally:
        kernel32.CloseHandle(snap)


def _attach_parent_console():
    """Give the built, windowed ``Electric.exe`` somewhere to print when it was
    started from a terminal (``--help``, ``--list``, snapshots). A double-click
    has no console to borrow, so nothing changes there.

    The one-file exe is two processes (PyInstaller's launcher, then Python), so
    the terminal is usually the grandparent. Same as the ASCII Visualizer's."""
    if os.name != "nt" or not getattr(sys, "frozen", False) or sys.stdout is not None:
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        attached = kernel32.AttachConsole(-1)       # ATTACH_PARENT_PROCESS
        if not attached:
            grandparent = _parent_pid(os.getppid())
            attached = grandparent is not None and kernel32.AttachConsole(grandparent)
        if not attached:
            return
        out = open("CONOUT$", "w", encoding=f"cp{kernel32.GetConsoleOutputCP()}", errors="replace")
        sys.stdout = sys.stderr = out
        print()     # the shell has already redrawn its prompt; start below it
    except Exception:
        pass


def _report_crash():
    """A windowed exe has nowhere to show a traceback: log it and say where."""
    from electric import config
    log = config.user_config_path().parent / "error.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"--- {' '.join(sys.argv)}\n{traceback.format_exc()}\n")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"Electric stopped with an error.\n\nDetails: {log}",
                                         "Electric", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    if getattr(sys, "frozen", False):
        _attach_parent_console()
    from electric.app import main
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        if getattr(sys, "frozen", False) and os.name == "nt":
            _report_crash()
            sys.exit(1)
        raise
