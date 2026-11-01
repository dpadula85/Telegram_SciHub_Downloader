import pytest

from doi_paper_downloader import cli


def _empty_env(tmp_path, monkeypatch):
    for key in ("TG_API_ID", "TG_API_HASH", "TG_TARGET"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "empty.env"
    env_file.write_text("")
    return env_file


def test_missing_configuration_exits_2(tmp_path, monkeypatch, capsys):
    env_file = _empty_env(tmp_path, monkeypatch)
    assert cli.main(["--env-file", str(env_file), "10.1000/x"]) == 2
    assert "Missing configuration" in capsys.readouterr().err


def test_no_valid_dois_exits_2(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / "ok.env"
    env_file.write_text("TG_API_ID=1\nTG_API_HASH=h\nTG_TARGET=@bot\n")
    for key in ("TG_API_ID", "TG_API_HASH", "TG_TARGET"):
        monkeypatch.delenv(key, raising=False)
    assert cli.main(["--env-file", str(env_file), "not-a-doi"]) == 2
    assert "no valid DOIs" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "doi-paper-downloader" in capsys.readouterr().out


def test_output_dir_flag_overrides_env_and_creates_folder(tmp_path, monkeypatch):
    for key in ("TG_API_ID", "TG_API_HASH", "TG_TARGET", "OUTPUT_DIR"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "ok.env"
    env_file.write_text(
        "TG_API_ID=1\nTG_API_HASH=h\nTG_TARGET=@bot\nOUTPUT_DIR=from_env\n")
    seen = {}

    async def fake_run_batch(settings, dois, store, force):
        seen["output_dir"] = settings.output_dir
        seen["dois"] = list(dois)
        return {"downloaded": len(dois)}

    monkeypatch.setattr(cli, "run_batch", fake_run_batch)
    dest = tmp_path / "chosen" / "papers"
    assert cli.main(["--env-file", str(env_file), "-o", str(dest),
                     "10.1000/x"]) == 0
    assert seen["output_dir"] == dest.resolve()
    assert seen["dois"] == ["10.1000/x"]
    assert (dest / "downloads.sqlite3").exists()
    assert (dest / "download_report.csv").exists()
    assert not (tmp_path / "from_env").exists()
