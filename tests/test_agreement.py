from typeless.agreement import LocalAgreement, Word, join_words, trim_point


def words(*items):
    """words("привет", "как") -> consecutive 0.5 s words."""
    return [Word(i * 0.5, i * 0.5 + 0.4, " " + t) for i, t in enumerate(items)]


def texts(ws):
    return [w.text.strip() for w in ws]


def test_first_hypothesis_confirms_nothing():
    la = LocalAgreement()
    confirmed, tail = la.update(words("привет", "как"))
    assert confirmed == [] and texts(tail) == ["привет", "как"]


def test_agreeing_prefix_is_confirmed_once():
    la = LocalAgreement()
    la.update(words("привет", "кот"))
    confirmed, tail = la.update(words("привет", "как", "дела"))
    assert texts(confirmed) == ["привет"] and texts(tail) == ["как", "дела"]
    confirmed, _ = la.update(words("привет", "как", "дела"))
    assert texts(confirmed) == ["как", "дела"]


def test_punctuation_change_still_agrees():
    la = LocalAgreement()
    la.update(words("привет", "мир"))
    confirmed, _ = la.update(words("Привет,", "мир"))
    assert texts(confirmed) == ["Привет,", "мир"]


def test_overlap_with_committed_tail_is_dropped():
    la = LocalAgreement()
    la.update(words("один", "два"))
    la.update(words("один", "два"))
    # after trimming the buffer the model may re-emit the last committed word
    shifted = [Word(0.85, 1.2, " два"), Word(1.3, 1.7, " три")]
    _, tail = la.update(shifted)
    assert texts(tail) == ["три"]


def test_flush_confirms_everything_new():
    la = LocalAgreement()
    la.update(words("раз", "два"))
    la.update(words("раз", "два", "три"))
    assert texts(la.flush(words("раз", "два", "три", "четыре"))) == ["три", "четыре"]


def test_trim_keeps_short_buffer():
    assert trim_point(words("Привет.", "как"), 0.0, buffer_s=4, soft=6, hard=12) is None


def test_trim_at_last_sentence_end_past_soft_limit():
    committed = words("Привет.", "как", "дела?", "хорошо")
    assert trim_point(committed, 0.0, buffer_s=7, soft=6, hard=12) == committed[2].end


def test_no_sentence_end_waits_until_hard_limit():
    committed = words("один", "два", "три")
    assert trim_point(committed, 0.0, buffer_s=8, soft=6, hard=12) is None
    assert trim_point(committed, 0.0, buffer_s=13, soft=6, hard=12) == committed[-1].end


def test_trim_ignores_words_already_cut():
    committed = words("Старое.", "новое")
    assert trim_point(committed, offset=1.0, buffer_s=7, soft=6, hard=12) is None


def test_join_words():
    assert join_words(words("Привет,", "как", "дела?")) == "Привет, как дела?"
