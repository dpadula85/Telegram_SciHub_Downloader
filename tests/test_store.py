import csv

from doi_paper_downloader.store import DownloadStore


def test_record_status_and_case_insensitive_lookup(tmp_path):
    with DownloadStore(tmp_path / "db.sqlite3") as store:
        assert store.status("10.1000/AbC") is None
        store.record("10.1000/AbC", "pending")
        store.record("10.1000/abc", "downloaded", "a.pdf", "ok")
        assert store.status("10.1000/ABC") == "downloaded"
        assert store.counts() == {"downloaded": 1}


def test_export_csv(tmp_path):
    with DownloadStore(tmp_path / "db.sqlite3") as store:
        store.record("10.1000/x", "timeout", message="No PDF within 5s")
        store.export_csv(tmp_path / "report.csv")
    rows = list(csv.DictReader((tmp_path / "report.csv").open()))
    assert rows[0]["doi"] == "10.1000/x"
    assert rows[0]["status"] == "timeout"
    assert rows[0]["message"] == "No PDF within 5s"
