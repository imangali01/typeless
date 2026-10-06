from typeless.cleanup import clean, is_hallucination


def test_removes_fillers():
    assert clean("Ээ, давай сделаем эм деплой") == "давай сделаем деплой"
    assert clean("ммм ну окей") == "ну окей"


def test_keeps_real_words():
    assert clean("Это этап, эмоции, мама") == "Это этап, эмоции, мама"


def test_hallucinations():
    assert is_hallucination("Продолжение следует...")
    assert is_hallucination("Субтитры сделал DimaTorzok")
    assert not is_hallucination("Спасибо, коллеги")
