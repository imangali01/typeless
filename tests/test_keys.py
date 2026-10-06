import pytest

from typeless.keys import DEFAULT_HOTKEY, Hotkey


def test_default_is_win_c():
    assert str(DEFAULT_HOTKEY) == "Win+C"
    assert Hotkey.parse("Win+C") == DEFAULT_HOTKEY


@pytest.mark.parametrize("text", ["Ctrl+Alt+Space", "F13", "Ctrl+Shift+F5", "Win+VK E8".replace(" ", "")])
def test_roundtrip(text):
    assert Hotkey.parse(str(Hotkey.parse(text))) == Hotkey.parse(text)


def test_modifier_order_is_canonical():
    assert str(Hotkey.parse("shift+win+ctrl+a")) == "Ctrl+Shift+Win+A"


@pytest.mark.parametrize("bad", ["", "Hyper+C", "Win+NoSuchKey"])
def test_parse_errors(bad):
    with pytest.raises(ValueError):
        Hotkey.parse(bad)
