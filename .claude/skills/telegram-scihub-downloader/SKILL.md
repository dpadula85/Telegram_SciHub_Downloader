---
name: telegram-scihub-downloader
description: Download the PDF of a scientific paper from its DOI with the Telegram_SciHub_Downloader tool (command `doi-paper-downloader`), which asks a configured Telegram bot/chat through the user's own Telegram account. Use whenever the user asks for the PDF or full text of a paper, gives DOIs or doi.org links to fetch, or when you need a paper's full text to answer and only have its DOI or citation. Covers how to run it, how to check the result, and the hard rules about the credential files (.env, *.session), which must never be read.
---

# Telegram_SciHub_Downloader

Sends each DOI to a Telegram bot/chat through the user's logged-in Telegram account and saves the returned PDF as `<DOI with / -> _>.pdf`. Full user documentation is in the repo `README.md`.

## Hard rules

- **Never read, print, copy or grep `.env`, `.env.*` (except `.env.example`) or `*.session*`.** They hold the Telegram API hash and a login that grants access to the whole account. Do not `cat`, `Read`, `head`, `grep`, `cp`, `rsync` or upload them, and do not put their contents in any command line, log or message. The tool reads them itself; you only pass `--env-file <path>` when needed.
- Never run `git add -A`/`git add .` blindly in the repo, and never remove those files from `.gitignore`.
- Never start a login yourself: the first-run prompt needs the user's phone code. Always run the tool with stdin closed (`< /dev/null`) so a missing or expired session fails at once instead of hanging, then ask the user to log in once from their own terminal.
- One request at a time, at most a few dozen DOIs per run; Telegram throttles bursts. Do not loop the tool over hundreds of DOIs without asking.
- The tool sends the user's account's messages to a third party. Only send DOIs the user asked for.

## Find the repo and the command

The repo root is three levels above this skill's resolved path:

```bash
REPO=$(readlink -f ~/.claude/skills/telegram-scihub-downloader/../../..)
```

Prefer the installed command `doi-paper-downloader`. If it is not on the PATH, run from the repo without installing (prepend, never assign, `PYTHONPATH`):

```bash
PYTHONPATH="$REPO:$PYTHONPATH" python3 -m doi_paper_downloader ...
```

Use `python3`, never `python`. Needs `telethon` and `python-dotenv` (`pip install -e "$REPO"` installs both).

## Settings

The tool finds `.env` by walking up from the current directory. Run from `$REPO`, or pass `--env-file "$REPO/.env"`. The session file and a relative `OUTPUT_DIR` then resolve next to that `.env`, whatever the cwd. The `-o` option below is what controls where PDFs go; it resolves against the cwd, not the `.env`. Check that the file exists with `test -f "$REPO/.env"` (an existence test, not a read). If it is missing, stop and tell the user to follow the README "Configuration" section.

## Fetch papers

1. Get clean DOIs. If the user gave a title or citation, resolve the DOI first (Crossref or the Scite tools) and confirm it matches before requesting. A DOI can also be given as a `https://doi.org/...` URL.
2. **Always pass the destination explicitly with `-o <folder>`**; the user chooses where PDFs go. Use the folder they named. If they did not say, use `papers/` in the current project and tell them where the files landed; ask first only if the right place is genuinely unclear (for example a paper meant for a specific manuscript or course folder). Use an absolute path, or a path relative to the directory you run from. The folder is created if missing; the PDFs, `downloads.sqlite3`, `download_report.csv` and the log all go inside it. Without `-o` the files go to `OUTPUT_DIR` from the user's `.env`, which is not necessarily where they want them.
3. Run, with stdin closed and a wall-clock limit above the per-DOI timeout (default 180 s per DOI, plus 3 s pause):

```bash
timeout 900 doi-paper-downloader --env-file "$REPO/.env" -o /path/to/destination \
    10.1038/s41586-020-2649-2 10.1021/jp400894v < /dev/null
```

The skip check is per output folder: a DOI already downloaded into a different folder is requested again, so reuse the same folder for a project, or copy the existing PDF instead of re-requesting.

For a list use `-i dois.txt` instead of DOIs on the command line. `--timeout SECONDS` overrides the per-DOI wait; `--force` requests again a DOI that is already downloaded; `-v` shows debug messages.

## Read the result

Each DOI prints one line: `[OK]` saved, `[SKIP]` already there, `[TIME]` no PDF in time, `[WAIT]` rate limit, `[ERR]` error. Then `Summary: ...` and the report path. Exit status: 0 all fine, 1 at least one failed, 2 bad configuration or input, 130 interrupted.

Per-DOI status is also in `<output>/download_report.csv` (columns `doi,status,filename,message,updated_at`) and `<output>/downloads.sqlite3`; debug log in `<output>/doi_paper_downloader.log`.

Report to the user which DOIs succeeded and which did not, with the status message.

## Verify before relying on a PDF

The tool checks only that the file is a PDF. A bot can return the wrong paper. For each downloaded file, extract the first page text (`pdftotext -l 1 file.pdf -` or the Read tool on the PDF, first pages only) and confirm the title/authors match the DOI's record before quoting it.

## When it fails

| Symptom | Cause and action |
| --- | --- |
| Exit 2, `Missing configuration` | no `.env` found: pass `--env-file`, or ask the user to create it (`.env.example` is the template) |
| Hangs or `EOFError` at a prompt | no valid session: do not try to log in. Tell the user to run the tool once from their terminal and enter the code |
| Exit 2, `cannot resolve TG_TARGET` | the bot/chat is unknown to the account: the user must open it once in the Telegram app |
| All `[TIME]` | the bot replies with text, not a PDF (unknown paper, link, other format). Rerun one DOI with `-v` and read the `reply without PDF:` lines in the log (text only, no credentials in it); raise `--timeout` if it is just slow |
| `[WAIT]` | Telegram rate limit: wait, rerun later with fewer DOIs; the batch resumes (finished DOIs are skipped) |

If a paper cannot be obtained, say so; do not try other download routes on your own.
