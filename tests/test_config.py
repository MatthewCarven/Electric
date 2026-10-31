import json

import pytest

from electric import app, config
from electric.config import Settings


def test_defaults_are_valid():
    clean, problems = config.validate(json.loads(config.dump(Settings())))
    assert problems == []
    assert Settings(**clean) == Settings()


def test_names_are_case_and_accent_blind():
    clean, problems = config.validate({"particle_type": "croutons", "palette": "NEON",
                                       "cycling": "Fast", "layout": "Tiling"})
    assert problems == []
    assert clean == {"particle_type": "Croûtons", "palette": "Neon", "cycling": "fast", "layout": "tiling"}
    assert Settings(particle_type="all").type_index == 0
    assert Settings(particle_type="All of them !").type_index == 0
    assert config.validate({"particle_type": "All of them !"})[0] == {"particle_type": "All"}


def test_bad_values_keep_their_defaults_and_say_why():
    clean, problems = config.validate({"palette": "Mauve", "blur": 99, "random_count": "yes",
                                       "particle_count": 2.5, "colour": "x", "_note": "ignored"})
    assert clean == {}
    assert len(problems) == 5
    assert any("unknown setting 'colour'" in p for p in problems)


def test_load_never_raises(isolated_config):
    bad = isolated_config / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    values, path, problems = config.load(bad)
    assert values == {} and path == bad and problems
    assert config.load(isolated_config / "nope.json")[0] == {}
    assert config.load() == ({}, None, [])


def test_search_order(isolated_config, monkeypatch):
    user = config.write(config.user_config_path(), Settings(palette="Alien"))
    assert config.find() == user
    env = config.write(isolated_config / "env.json", Settings(palette="Neon"))
    monkeypatch.setenv("ELECTRIC_CONFIG", str(env))
    assert config.find() == env
    explicit = config.write(isolated_config / "x.json", Settings())
    assert config.find(explicit) == explicit


def test_command_line_beats_file_beats_defaults(isolated_config):
    path = config.write(isolated_config / "c.json", Settings(palette="Alien", blur=3, reverse=True))
    settings, opts, found, problems = app.parse(["--config", str(path), "--palette", "neon",
                                                 "--no-reverse", "--type", "Jambons"])
    assert found == path and problems == []
    assert settings.palette == "Neon"           # flag
    assert settings.blur == 3                   # file
    assert settings.reverse is False            # flag over file
    assert settings.particle_type == "Jambons"
    assert settings.crossfade_seconds == Settings().crossfade_seconds   # default


def test_command_line_rejects_bad_values():
    with pytest.raises(SystemExit):
        app.parse(["--blur", "100"])
    with pytest.raises(SystemExit):
        app.parse(["--palette", "Mauve"])


def test_write_config_round_trips(isolated_config):
    target = isolated_config / "out.json"
    assert app.main(["--write-config", str(target), "--palette", "Gaudy", "--text", "HI"]) == 0
    values, _, problems = config.load(target)
    assert problems == [] and values["palette"] == "Gaudy" and values["text"] == "HI"
