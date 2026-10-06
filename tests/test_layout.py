from typeless.layout import is_english


def test_english_layouts():
    assert is_english(0x04090409)  # en-US
    assert is_english(0x08090809)  # en-GB


def test_other_layouts_are_not_english():
    assert not is_english(0x04190419)  # ru-RU
    assert not is_english(0x043F043F)  # kk-KZ
    assert not is_english(0)
