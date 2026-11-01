"""wait_for_pdf / process_doi against a fake Telegram client (no network)."""

import asyncio
from types import SimpleNamespace

from doi_paper_downloader.config import Settings
from doi_paper_downloader.fetcher import is_pdf_document, process_doi, wait_for_pdf
from doi_paper_downloader.store import DownloadStore


def make_msg(msg_id, payload=None, mime="application/pdf", name="x.pdf",
             text="", out=False):
    document = None
    if payload is not None:
        attrs = [SimpleNamespace(file_name=name)] if name else []
        document = SimpleNamespace(mime_type=mime, attributes=attrs)
    return SimpleNamespace(id=msg_id, document=document, message=text, out=out,
                           payload=payload)


class FakeClient:
    """Serves ``replies`` for messages newer than the request."""

    def __init__(self, replies):
        self.replies = replies
        self.downloads = []
        self._next_id = 100

    async def send_message(self, entity, text):
        self._next_id += 1
        return SimpleNamespace(id=self._next_id)

    async def iter_messages(self, entity, min_id, reverse, limit):
        for msg in self.replies:
            yield msg

    async def download_media(self, msg, file):
        self.downloads.append(msg.id)
        with open(file, "wb") as handle:
            handle.write(msg.payload)
        return file


def run(coro):
    return asyncio.run(coro)


def test_is_pdf_document():
    assert is_pdf_document(make_msg(1, b"x"))
    assert is_pdf_document(make_msg(1, b"x", mime="application/octet-stream", name="a.PDF"))
    assert not is_pdf_document(make_msg(1, b"x", mime="image/png", name="a.png"))
    assert not is_pdf_document(make_msg(1, text="hello"))


def test_wait_for_pdf_downloads_valid_pdf(tmp_path):
    client = FakeClient([make_msg(101, text="working..."), make_msg(102, b"%PDF-1.7 body")])
    dest = tmp_path / "p.pdf"
    assert run(wait_for_pdf(client, None, 100, dest, timeout=2, poll_interval=0.01)) == dest
    assert dest.read_bytes().startswith(b"%PDF-")
    assert list(tmp_path.iterdir()) == [dest]


def test_wait_for_pdf_rejected_document_is_downloaded_once(tmp_path):
    client = FakeClient([make_msg(101, b"<html>not a pdf</html>")])
    dest = tmp_path / "p.pdf"
    assert run(wait_for_pdf(client, None, 100, dest, timeout=0.3, poll_interval=0.01)) is None
    assert client.downloads == [101]
    assert list(tmp_path.iterdir()) == []


def test_wait_for_pdf_ignores_own_messages(tmp_path):
    client = FakeClient([make_msg(101, b"%PDF-1.7", out=True)])
    assert run(wait_for_pdf(client, None, 100, tmp_path / "p.pdf",
                            timeout=0.2, poll_interval=0.01)) is None
    assert client.downloads == []


def _settings(tmp_path, timeout=0.3):
    return Settings(api_id=1, api_hash="h", target="@bot", output_dir=tmp_path,
                    session=tmp_path / "s", timeout=timeout, poll_interval=0.01)


def test_process_doi_download_skip_and_force(tmp_path):
    settings = _settings(tmp_path)
    client = FakeClient([make_msg(101, b"%PDF-1.7 v1")])
    with DownloadStore(tmp_path / "db.sqlite3") as store:
        assert run(process_doi(client, None, store, "10.1000/x", settings)) == "downloaded"
        assert store.status("10.1000/x") == "downloaded"
        assert run(process_doi(client, None, store, "10.1000/x", settings)) == "skipped"
        assert client.downloads == [101]

        client.replies = [make_msg(102, b"%PDF-1.7 v2")]
        assert run(process_doi(client, None, store, "10.1000/x", settings, force=True)) == "downloaded"
    assert (tmp_path / "10.1000_x.pdf").read_bytes() == b"%PDF-1.7 v2"


def test_process_doi_timeout(tmp_path):
    client = FakeClient([make_msg(101, text="DOI not found")])
    with DownloadStore(tmp_path / "db.sqlite3") as store:
        assert run(process_doi(client, None, store, "10.1000/y", _settings(tmp_path))) == "timeout"
        assert store.status("10.1000/y") == "timeout"
