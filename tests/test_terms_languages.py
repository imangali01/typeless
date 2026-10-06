from typeless.cleanup import apply_corrections
from typeless.languages import CODER_TERMS, build_prompt
from typeless.terms import suggest_terms


def test_suggest_latin_words_not_in_dictionary():
    text = "Обновил Terraform и Helm chart, потом сделал commit в GitHub. Ok"
    assert suggest_terms(text, known=["helm"]) == ["Terraform", "chart"]


def test_suggest_nothing_for_plain_russian():
    assert suggest_terms("Привет, как дела?", known=[]) == []


def test_corrections_whole_words_case_insensitive():
    fixes = {"ттермен": "термин", "кубернитис": "Kubernetes"}
    assert apply_corrections("Ттермен и кубернитис, ттермены", fixes) == "Термин и Kubernetes, ттермены"


def test_prompt_contains_seed_terms_and_profile():
    prompt = build_prompt("ru_en", "coder", ["Terraform"], recent="")
    assert prompt.startswith("Сделал commit")
    assert "Terraform" in prompt and "Kubernetes" in prompt


def test_prompt_plain_russian_skips_coder_terms():
    assert "Kubernetes" not in build_prompt("ru", "coder", [], "")


def test_prompt_is_bounded():
    assert len(build_prompt("ru_en", "coder", ["x" * 10] * 80, recent="слова " * 100)) <= 700


def test_prompt_keeps_recent_tail_when_room():
    assert build_prompt("ru", "general", [], recent="последние слова").endswith("последние слова")


def test_coder_terms_are_unique():
    assert len({t.lower() for t in CODER_TERMS}) == len(CODER_TERMS)
