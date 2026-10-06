from typeless.app_rules import DEFAULT_RULES, combo_vks, match
from typeless.keys import Hotkey


def test_vs_code_sends_ctrl_d():
    hk = match(DEFAULT_RULES, "Code.exe")
    assert hk == Hotkey.parse("Ctrl+D")
    assert combo_vks(hk) == [0xA2, ord("D")]  # left Ctrl, D


def test_match_is_case_insensitive_and_misses_other_apps():
    assert match({"code.exe": "Ctrl+D"}, "Code.exe") is not None
    assert match(DEFAULT_RULES, "chrome.exe") is None


def test_broken_rule_is_ignored():
    assert match({"Code.exe": "Hyper+D"}, "Code.exe") is None
    assert match({"Code.exe": ""}, "Code.exe") is None


def test_modifier_order():
    assert combo_vks(Hotkey.parse("Shift+Ctrl+Alt+V")) == [0xA2, 0xA4, 0xA0, ord("V")]
