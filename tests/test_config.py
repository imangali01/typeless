import json

from typeless.config import ENGINE_GIGAAM, ENGINE_PARAKEET, ENGINE_WHISPER, Config


def load(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return Config.load(path)


def test_old_whisper_and_windows_configs_move_to_parakeet(tmp_path):
    assert load(tmp_path, {"engine": "whisper"}).engine == ENGINE_PARAKEET
    assert load(tmp_path, {"engine": "windows"}).engine == ENGINE_PARAKEET


def test_choice_made_after_migration_is_kept(tmp_path):
    assert load(tmp_path, {"engine": ENGINE_WHISPER, "version": 2}).engine == ENGINE_WHISPER
    assert load(tmp_path, {"engine": ENGINE_GIGAAM, "version": 2}).engine == ENGINE_GIGAAM


def test_saved_config_round_trips(tmp_path):
    path = tmp_path / "config.json"
    Config(engine=ENGINE_WHISPER).save(path)
    assert Config.load(path).engine == ENGINE_WHISPER
