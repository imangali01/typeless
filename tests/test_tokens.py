from pytest import approx

from typeless.engines.onnx import tokens_to_words


def test_subword_tokens_join_into_words_with_punctuation():
    tokens = [" При", "вет", "!", " Се", "го", "дня"]
    stamps = [0.0, 0.32, 0.64, 0.8, 0.96, 1.12]
    words = tokens_to_words(tokens, stamps, offset=10.0, audio_s=2.0)
    assert [w.text for w in words] == [" Привет!", " Сегодня"]
    assert words[0].start == 10.0 and words[0].end == 10.8
    assert words[1].end == approx(10.0 + 1.12 + 0.3)


def test_lone_space_tokens_gigaam_style():
    tokens = [" П", "ри", " ", "я", " ", "х", "о"]
    stamps = [0.0, 0.28, 1.36, 1.44, 1.48, 1.56, 1.6]
    words = tokens_to_words(tokens, stamps, offset=0.0, audio_s=1.7)
    assert [w.text for w in words] == [" При", " я", " хо"]
    assert words[1].start == 1.44 and words[2].start == 1.56
    assert words[2].end == 1.7  # capped at the end of the audio
