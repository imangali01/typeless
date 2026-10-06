from typeless import winapi as w
from typeless.live_text import Edit
from typeless.typer import VK_BACK, build_events

UP = w.KEYEVENTF_KEYUP
UNI = w.KEYEVENTF_UNICODE


def test_backspaces_then_unicode_text():
    events = build_events(Edit(backspaces=1, text="Щ"))
    assert events == [
        (VK_BACK, 0, 0), (VK_BACK, 0, UP),
        (0, ord("Щ"), UNI), (0, ord("Щ"), UNI | UP),
    ]


def test_surrogate_pair_is_two_code_units():
    events = build_events(Edit(text="😀"))
    assert [scan for _, scan, flags in events if not flags & UP] == [0xD83D, 0xDE00]


def test_empty_edit_has_no_events():
    assert build_events(Edit()) == []
