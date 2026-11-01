"""fetcher.py - send DOIs to a Telegram bot/chat and collect the returned PDFs.

Telegram is used through a *user account* (Telethon), not a bot token: the
first run asks interactively for the phone number, login code and, if
enabled, the 2FA password, and stores the login in a ``.session`` file.

For each DOI the DOI is sent as a plain message; only messages newer than
that request are inspected, so an old attachment cannot be mistaken for the
current answer. A document is accepted only if it is a PDF by MIME type or
file name *and* starts with the ``%PDF-`` signature. One DOI is handled at a
time, so replies from a bot that answers asynchronously cannot be mixed up.
"""

import asyncio
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Sequence, Set, Union

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

from .config import Settings
from .dois import safe_filename
from .store import DownloadStore

log = logging.getLogger(__name__)

PDF_SIGNATURE = b"%PDF-"
#: Messages fetched per poll; the answer to one DOI is a handful at most.
_POLL_LIMIT = 100


def is_pdf_document(msg) -> bool:
    """True if ``msg`` carries a document that is a PDF by MIME type or file name."""
    document = getattr(msg, "document", None)
    if document is None:
        return False
    if (document.mime_type or "").lower() == "application/pdf":
        return True
    names = [
        getattr(attr, "file_name", None) for attr in document.attributes or []
    ]
    return any(name.lower().endswith(".pdf") for name in names if name)


async def _download_pdf(client: TelegramClient, msg, destination: Path) -> bool:
    """Download ``msg`` next to ``destination`` and move it into place if it is a PDF."""
    temp = destination.with_name(f".{destination.name}.download")
    downloaded: Optional[Path] = None
    try:
        result = await client.download_media(msg, file=str(temp))
        if not result:
            return False
        downloaded = Path(result)
        with downloaded.open("rb") as handle:
            signature = handle.read(len(PDF_SIGNATURE))
        if signature != PDF_SIGNATURE:
            log.warning("message %d: document is not a PDF (bad signature)", msg.id)
            return False
        downloaded.replace(destination)
        return True
    finally:
        temp.unlink(missing_ok=True)
        if downloaded is not None:
            downloaded.unlink(missing_ok=True)


async def wait_for_pdf(
    client: TelegramClient,
    entity,
    after_message_id: int,
    destination: Path,
    timeout: float,
    poll_interval: float,
) -> Optional[Path]:
    """Poll messages newer than ``after_message_id`` until a valid PDF arrives.

    Returns ``destination`` on success and None after ``timeout`` seconds.
    Every message is examined once; a rejected one is not downloaded again.
    """
    deadline = time.monotonic() + timeout
    seen: Set[int] = set()

    while time.monotonic() < deadline:
        try:
            async for msg in client.iter_messages(
                entity, min_id=after_message_id, reverse=True, limit=_POLL_LIMIT
            ):
                if msg.out or msg.id in seen:
                    continue
                seen.add(msg.id)
                if not is_pdf_document(msg):
                    log.debug("reply without PDF: %r", (msg.message or "")[:200])
                    continue
                if await _download_pdf(client, msg, destination):
                    return destination
        except FloodWaitError as exc:
            log.warning("rate limited while polling: waiting %d s", exc.seconds)
            await asyncio.sleep(exc.seconds + 1)
        await asyncio.sleep(poll_interval)

    return None


async def process_doi(
    client: TelegramClient,
    entity,
    store: DownloadStore,
    doi: str,
    settings: Settings,
    force: bool = False,
) -> str:
    """Request one DOI and record the outcome. Returns the status string."""
    destination = settings.output_dir / f"{safe_filename(doi)}.pdf"

    if not force and store.status(doi) == "downloaded" and destination.exists():
        print(f"[SKIP] {doi} (already downloaded)")
        return "skipped"

    print(f"[SEND] {doi}")
    store.record(doi, "pending", message="DOI sent; waiting for PDF")

    try:
        sent = await client.send_message(entity, doi)
        path = await wait_for_pdf(
            client, entity, sent.id, destination,
            timeout=settings.timeout, poll_interval=settings.poll_interval,
        )
    except FloodWaitError as exc:
        message = f"Telegram rate limit: wait {exc.seconds}s"
        print(f"[WAIT] {doi}: {message}")
        store.record(doi, "rate_limited", message=message)
        await asyncio.sleep(exc.seconds + 1)
        return "rate_limited"
    except (RPCError, OSError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        print(f"[ERR]  {doi}: {message}")
        store.record(doi, "error", message=message)
        return "error"

    if path is None:
        message = f"No PDF within {settings.timeout:g}s"
        print(f"[TIME] {doi} ({message})")
        store.record(doi, "timeout", message=message)
        return "timeout"

    print(f"[OK]   {doi} -> {path}")
    store.record(doi, "downloaded", str(path), "PDF received and validated")
    return "downloaded"


def _target_entity(target: str) -> Union[int, str]:
    """Numeric chat IDs must be passed to Telethon as int, usernames as str."""
    return int(target) if target.lstrip("-").isdigit() else target


def _protect_session(session: Path) -> None:
    """Make the login file readable by the owner only: it grants account access."""
    path = session.with_name(session.name + ".session")
    try:
        path.chmod(0o600)
    except OSError as exc:
        log.warning("could not restrict permissions on %s: %s", path, exc)


async def run_batch(
    settings: Settings,
    dois: Sequence[str],
    store: DownloadStore,
    force: bool = False,
) -> Dict[str, int]:
    """Process ``dois`` in order; returns the number of DOIs per outcome."""
    outcomes: Counter = Counter()
    client = TelegramClient(str(settings.session), settings.api_id, settings.api_hash)
    # Entering the context manager starts the client (interactive login on first run).
    async with client:
        _protect_session(settings.session)
        try:
            entity = await client.get_entity(_target_entity(settings.target))
        except ValueError as exc:
            raise ValueError(
                f"cannot resolve TG_TARGET {settings.target!r}: {exc}. Open the "
                "bot or chat once in the Telegram app and check the spelling."
            ) from exc
        print(f"Telegram connected. Target: {settings.target}")
        print(f"DOIs queued: {len(dois)}")
        for index, doi in enumerate(dois, start=1):
            print(f"\n[{index}/{len(dois)}]")
            outcomes[await process_doi(client, entity, store, doi, settings, force)] += 1
            if index < len(dois):
                await asyncio.sleep(settings.pause_between_dois)
    return dict(outcomes)
