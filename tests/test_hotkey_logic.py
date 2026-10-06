from typeless.hotkey_logic import Decision, HotkeyMatcher
from typeless.keys import DEFAULT_HOTKEY, Hotkey

LWIN, LCTRL, LALT, C, H = 0x5B, 0xA2, 0xA4, ord("C"), ord("H")


def test_win_c_is_swallowed_and_triggers_once():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    assert not m.on_event(LWIN, True).suppress
    down = m.on_event(C, True)
    assert down.suppress and down.triggered and down.inject_mask
    repeat = m.on_event(C, True)
    assert repeat.suppress and not repeat.triggered
    assert m.on_event(C, False).suppress
    assert not m.on_event(LWIN, False).suppress


def test_plain_c_and_other_win_combos_pass():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    assert not m.on_event(C, True).suppress
    assert not m.on_event(C, False).suppress
    m.on_event(LWIN, True)
    assert not m.on_event(H, True).suppress


def test_extra_modifier_does_not_match():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    m.on_event(LWIN, True)
    m.on_event(LCTRL, True)
    assert not m.on_event(C, True).triggered


def test_capture_reports_combo_and_swallows_it():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    m.capturing = True
    m.on_event(LCTRL, True)
    m.on_event(LALT, True)
    d = m.on_event(ord("D"), True)
    assert d.suppress and d.captured == Hotkey(frozenset({"ctrl", "alt"}), ord("D"))
    assert d.inject_mask
    assert not m.capturing
    assert m.on_event(ord("D"), False).suppress


ENTER, LSHIFT = 0x0D, 0xA0


def test_enter_passes_when_not_dictating():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    assert m.on_event(ENTER, True) == Decision()


def test_enter_is_swallowed_while_dictating():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    m.intercept_enter = True
    d = m.on_event(ENTER, True)
    assert d.suppress and d.enter and not d.triggered
    assert m.on_event(ENTER, False).suppress


def test_shift_enter_still_passes_while_dictating():
    m = HotkeyMatcher(DEFAULT_HOTKEY)
    m.intercept_enter = True
    m.on_event(LSHIFT, True)
    assert not m.on_event(ENTER, True).suppress


def test_hotkey_without_modifiers():
    f13 = Hotkey(frozenset(), 0x7C)
    m = HotkeyMatcher(f13)
    d = m.on_event(0x7C, True)
    assert d.triggered and not d.inject_mask
