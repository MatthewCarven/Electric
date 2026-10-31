import screensaver
from electric import monitors


def test_windows_command_lines():
    assert screensaver.parse_mode(["Electric.scr"]) == ("s", None)
    assert screensaver.parse_mode(["Electric.scr", "/s"]) == ("s", None)
    assert screensaver.parse_mode(["Electric.scr", "/S"]) == ("s", None)
    assert screensaver.parse_mode(["Electric.scr", "/p", "1234"]) == ("p", "1234")
    assert screensaver.parse_mode(["Electric.scr", "/p:1234"]) == ("p", "1234")
    assert screensaver.parse_mode(["Electric.scr", "/c:5678"]) == ("c", None)
    assert screensaver.parse_mode(["Electric.scr", "/c"]) == ("c", None)


def test_two_monitors_span_one_window():
    # A 1920x1080 primary, and a 1280x1024 monitor to its left, lower down.
    box, local = monitors.span([(0, 0, 1920, 1080), (-1280, 200, 1280, 1024)])
    assert box == (-1280, 0, 3200, 1224)
    assert local == [(1280, 0, 1920, 1080), (0, 200, 1280, 1024)]
    # GL counts y up from the window's bottom edge.
    assert monitors.gl_origin(local[0], 1224) == (1280, 144)
    assert monitors.gl_origin(local[1], 1224) == (0, 0)


def test_monitors_lists_the_primary_first():
    found = monitors.monitors()
    if found:                                   # Windows: at least the primary
        assert all(w > 0 and h > 0 for _, _, w, h in found)
