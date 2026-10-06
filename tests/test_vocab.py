from typeless.vocab import fix_terms, vocabulary


def test_near_miss_snaps_to_dictionary_term():
    assert fix_terms("читает данные из ClickHourse.", ["ClickHouse"]) == "читает данные из ClickHouse."


def test_case_is_taken_from_dictionary():
    assert fix_terms("выложу на github и обновлю Readme", ["GitHub", "README"]) == \
        "выложу на GitHub и обновлю README"


def test_short_and_distant_words_are_left_alone():
    terms = ["test", "Python", "Kubernetes"]
    assert fix_terms("text и Pandas", terms) == "text и Pandas"


def test_russian_words_are_never_touched():
    assert fix_terms("кликхаус и питон", ["ClickHouse", "Python"]) == "кликхаус и питон"


def test_vocabulary_adds_coder_terms_and_skips_phrases():
    terms = vocabulary(["Yelnur"], "coder")
    assert "Yelnur" in terms and "Kubernetes" in terms and "pull request" not in terms
    assert vocabulary(["Yelnur"], "general") == ["Yelnur"]
