from pathlib import Path

import pytest

from doi_paper_downloader.config import Settings, load_settings

ENV = {"TG_API_ID": "12345", "TG_API_HASH": "abc", "TG_TARGET": "@some_bot"}


def test_defaults_resolve_against_base_dir(tmp_path):
    s = Settings.from_mapping(ENV, tmp_path)
    assert s.api_id == 12345
    assert s.output_dir == tmp_path / "papers"
    assert s.session == tmp_path / "doi_downloader"
    assert s.timeout == 180.0


def test_overrides_and_absolute_paths(tmp_path):
    env = dict(ENV, OUTPUT_DIR=str(tmp_path / "out"), RESPONSE_TIMEOUT="60",
               PAUSE_BETWEEN_DOIS="0")
    s = Settings.from_mapping(env, Path("/nonexistent"))
    assert s.output_dir == tmp_path / "out"
    assert s.timeout == 60.0
    assert s.pause_between_dois == 0.0


def test_missing_keys_are_all_named(tmp_path):
    with pytest.raises(ValueError, match="TG_API_HASH, TG_TARGET"):
        Settings.from_mapping({"TG_API_ID": "1"}, tmp_path)


@pytest.mark.parametrize("key, value, match", [
    ("TG_API_ID", "abc", "TG_API_ID must be an integer"),
    ("RESPONSE_TIMEOUT", "soon", "RESPONSE_TIMEOUT must be a number"),
    ("RESPONSE_TIMEOUT", "-5", "timeout must be positive"),
    ("POLL_INTERVAL", "0", "poll_interval must be positive"),
])
def test_invalid_values(tmp_path, key, value, match):
    with pytest.raises(ValueError, match=match):
        Settings.from_mapping(dict(ENV, **{key: value}), tmp_path)


def test_load_settings_reads_env_file_and_anchors_paths(tmp_path, monkeypatch):
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "cfg" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("TG_API_ID=7\nTG_API_HASH=h\nTG_TARGET=@bot\nOUTPUT_DIR=pdfs\n")
    s = load_settings(env_file)
    assert s.api_id == 7
    assert s.output_dir == env_file.parent / "pdfs"


def test_load_settings_missing_env_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.env")
