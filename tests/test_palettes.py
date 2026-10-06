from typeless.overlay.palettes import PRESETS, STYLE_DEFAULTS, resolve


def test_style_default_when_nothing_chosen():
    assert resolve("drop", None) == PRESETS[STYLE_DEFAULTS["drop"]]


def test_preset_by_key():
    assert resolve("line", "amber") == PRESETS["amber"]


def test_custom_hex_builds_lighter_and_darker_shades():
    pal = resolve("pill", "#3366cc")
    assert pal.main == "#3366cc"
    assert pal.light != pal.main != pal.deep


def test_unknown_value_falls_back_to_default():
    assert resolve("ring", "nope") == PRESETS[STYLE_DEFAULTS["ring"]]
