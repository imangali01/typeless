from typeless.live_text import Edit, LiveText


def test_types_stable_words_and_holds_back_last():
    lt = LiveText()
    assert lt.on_hypothesis("привет") == Edit()
    assert lt.on_hypothesis("привет как") == Edit(text="привет")
    assert lt.on_hypothesis("привет как дела") == Edit(text=" как")


def test_final_corrects_typed_phrase():
    lt = LiveText()
    lt.on_hypothesis("привет как дела")  # typed "привет как"
    assert lt.on_final("Привет, как дела?") == Edit(backspaces=10, text="Привет, как дела?")


def test_final_keeps_common_prefix():
    lt = LiveText()
    lt.on_hypothesis("Привет как дела")  # typed "Привет как"
    assert lt.on_final("Привет, как дела?") == Edit(backspaces=4, text=", как дела?")


def test_second_phrase_gets_leading_space():
    lt = LiveText()
    lt.on_final("Первая фраза.")
    assert lt.on_hypothesis("вторая фраза тут") == Edit(text=" вторая фраза")
    assert lt.on_final("Вторая фраза тут.") == Edit(backspaces=12, text="Вторая фраза тут.")


def test_revised_hypothesis_waits_for_final():
    lt = LiveText()
    lt.on_hypothesis("код на python")  # typed "код на"
    assert lt.on_hypothesis("кот на python пишет") == Edit()


def test_rejected_final_erases_typed_text():
    lt = LiveText()
    lt.on_hypothesis("шум шум")
    assert lt.on_final("") == Edit(backspaces=3)


def test_not_live_types_only_finals():
    lt = LiveText(live=False)
    assert lt.on_hypothesis("привет как дела") == Edit()
    assert lt.on_final("Привет, как дела?") == Edit(text="Привет, как дела?")


def test_display_splits_confirmed_and_tail():
    lt = LiveText()
    lt.on_final("Первая.")
    lt.on_hypothesis("вторая фраза")
    assert lt.display() == ("Первая. вторая", "фраза")
