"""cli.py - command-line entry point (``doi-paper-downloader``).

DOIs come from the command line or, if none are given, from ``--input``.
Exit status: 0 all DOIs downloaded or already present, 1 at least one DOI
failed (timeout, rate limit, error), 2 bad configuration or input,
130 interrupted.
"""

import argparse as arg
import asyncio
import dataclasses
import logging
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import load_settings
from .dois import normalize_doi, read_dois
from .fetcher import run_batch
from .store import DownloadStore

log = logging.getLogger(__package__)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATEFMT = "%d-%m-%Y %H:%M:%S"
DEFAULT_LOG_NAME = "doi_paper_downloader.log"

_EPILOG = """\
examples:
  doi-paper-downloader 10.1038/s41586-020-2649-2
  doi-paper-downloader -i dois.txt -o ~/papers
  doi-paper-downloader --env-file ~/.config/doi/.env --timeout 300 -i dois.txt
"""


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Warnings and errors to stderr (everything with ``verbose``); full log to ``log_file``."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)
    log.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(console)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATEFMT))
        root.addHandler(file_handler)


def build_parser() -> arg.ArgumentParser:
    parser = arg.ArgumentParser(
        prog="doi-paper-downloader",
        description="Download paper PDFs by DOI through a Telegram bot/chat.",
        epilog=_EPILOG,
        formatter_class=arg.RawDescriptionHelpFormatter,
    )
    parser.add_argument("dois", nargs="*", metavar="DOI",
                        help="DOIs or doi.org URLs to fetch (default: read --input)")
    parser.add_argument("-i", "--input", type=Path, default=Path("dois.txt"),
                        help="text file with one DOI per line, used when no DOI is "
                             "given on the command line (default: dois.txt)")
    parser.add_argument("-o", "--output-dir", type=Path,
                        help="where PDFs, the database and the CSV report go "
                             "(default: OUTPUT_DIR from .env, else papers/)")
    parser.add_argument("--timeout", type=float,
                        help="seconds to wait for a PDF per DOI "
                             "(default: RESPONSE_TIMEOUT from .env, else 180)")
    parser.add_argument("--env-file", type=Path,
                        help="settings file (default: nearest .env above the cwd)")
    parser.add_argument("--force", action="store_true",
                        help="request DOIs again even if already downloaded")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print debug messages to the console")
    parser.add_argument("--log-file", type=Path,
                        help=f"debug log (default: <output-dir>/{DEFAULT_LOG_NAME})")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    return parser


def _collect_dois(args: arg.Namespace) -> List[str]:
    if not args.dois:
        return read_dois(args.input)
    found: List[str] = []
    for raw in args.dois:
        doi = normalize_doi(raw)
        if doi is None:
            log.warning("not a DOI, skipped: %s", raw)
        elif doi.lower() not in {d.lower() for d in found}:
            found.append(doi)
    return found


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    try:
        settings = load_settings(args.env_file)
        if args.output_dir is not None:
            settings = dataclasses.replace(
                settings, output_dir=args.output_dir.expanduser().resolve())
        if args.timeout is not None:
            settings = dataclasses.replace(settings, timeout=args.timeout)
        dois = _collect_dois(args)
    except (FileNotFoundError, ValueError) as exc:
        log.error("%s", exc)
        return 2
    if not dois:
        log.error("no valid DOIs to process")
        return 2

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(args.verbose, args.log_file or settings.output_dir / DEFAULT_LOG_NAME)

    try:
        with DownloadStore(settings.output_dir / "downloads.sqlite3") as store:
            try:
                outcomes = asyncio.run(run_batch(settings, dois, store, args.force))
            finally:
                report = settings.output_dir / "download_report.csv"
                store.export_csv(report)
    except KeyboardInterrupt:
        print("\nInterrupted. Run again to resume the batch.")
        return 130
    except ValueError as exc:
        log.error("%s", exc)
        return 2
    except EOFError:
        log.error("Telegram asked for a login code or password but there is no "
                  "terminal input. Run the command once interactively to log in.")
        return 2

    summary = ", ".join(f"{n} {status}" for status, n in sorted(outcomes.items()))
    print(f"\nSummary: {summary}")
    print(f"Report: {report}")
    return 0 if set(outcomes) <= {"downloaded", "skipped"} else 1
