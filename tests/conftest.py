import os

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Never read or write Matthew's real settings: point every config lookup
    at an empty temp folder (the env var, APPDATA, and beside-the-program)."""
    monkeypatch.setenv("ELECTRIC_CONFIG", str(tmp_path / "missing.json"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from electric import config
    monkeypatch.setattr(config, "program_dir", lambda: tmp_path / "program")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    return tmp_path
