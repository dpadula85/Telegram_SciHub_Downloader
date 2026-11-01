# Telegram_SciHub_Downloader

Command `doi-paper-downloader`. Get the PDF of a paper from its DOI, in bulk, through a Telegram bot or chat.

Some Telegram bots and chats answer a message containing a DOI with the PDF of
the paper. This tool automates that conversation: it logs in to Telegram as
you, sends each DOI, waits for the reply, checks that the attachment really is
a PDF, and saves it as `<DOI>.pdf`. The tool itself only talks to the bot or
chat you configure; make sure you are allowed to use it and to obtain the
papers (publisher terms, copyright, your institution's rules).

## Requirements

- Python 3.10 or newer.
- A Telegram account (a phone number that can receive the login code).
- Telegram API credentials (`api_id`, `api_hash`): log in at
  <https://my.telegram.org>, open "API development tools" and create an
  application. Any name works.
- A bot or chat that replies to a DOI with a PDF document. Which one to use is
  up to you; the tool does not ship one.

## Installation

```bash
git clone https://github.com/dpadula85/Telegram_SciHub_Downloader.git
cd Telegram_SciHub_Downloader
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

This installs the `doi-paper-downloader` command. `pip install -e ".[dev]"`
adds `pytest`.

## Configuration

Copy the template and fill it in:

```bash
cp .env.example .env
```

| Key | Meaning | Default |
| --- | --- | --- |
| `TG_API_ID` | numeric API ID from my.telegram.org | required |
| `TG_API_HASH` | API hash from my.telegram.org | required |
| `TG_TARGET` | the bot or chat: `@username` or a numeric chat ID | required |
| `OUTPUT_DIR` | where PDFs, the database and the report go | `papers` |
| `TG_SESSION` | name of the login file (`<name>.session`) | `doi_downloader` |
| `RESPONSE_TIMEOUT` | seconds to wait for a PDF per DOI | `180` |
| `POLL_INTERVAL` | seconds between checks for new messages | `3` |
| `PAUSE_BETWEEN_DOIS` | seconds between two requests | `3` |

Relative paths are relative to the folder that contains the `.env` file. The
command looks for `.env` in the current folder and the folders above it; use
`--env-file path/to/.env` to point elsewhere. Variables already set in your
shell win over the file.

### Keep two files private

`.env` and the `.session` file together give full access to your Telegram
account. Never commit, upload or share them. `.gitignore` already excludes
them; the tool also restricts the `.session` file to your user (mode 600).

## Usage

First run: Telegram asks in the terminal for your phone number, the code it
sends you and, if enabled, your 2FA password. After that the login is stored
in the `.session` file and no prompt appears again.

```bash
doi-paper-downloader 10.1038/s41586-020-2649-2          # DOIs on the command line
doi-paper-downloader -i dois.txt -o ~/papers            # DOIs from a file
python3 -m doi_paper_downloader -i dois.txt             # same, without installing the command
```

The input file has one DOI per line; `https://doi.org/...` URLs and `doi:`
prefixes are accepted, `#` starts a comment, duplicates are ignored (see
[dois.example.txt](dois.example.txt)).

Options (`doi-paper-downloader --help`):

| Option | Meaning |
| --- | --- |
| `DOI ...` | DOIs or URLs to fetch; if none, `--input` is read |
| `-i`, `--input` | file with one DOI per line (default `dois.txt`) |
| `-o`, `--output-dir` | folder for the PDFs (created if missing); overrides `OUTPUT_DIR`; a relative path is relative to where you run the command |
| `--timeout` | overrides `RESPONSE_TIMEOUT` (seconds) |
| `--env-file` | settings file instead of the nearest `.env` |
| `--force` | request DOIs again even if already downloaded |
| `-v`, `--verbose` | debug messages on the console |
| `--log-file` | debug log (default `<output-dir>/doi_paper_downloader.log`) |

### What you get

DOIs are sent one at a time; each prints one result line:

| Line | Meaning |
| --- | --- |
| `[SEND]` | DOI sent, waiting for the PDF |
| `[OK]` | PDF saved |
| `[SKIP]` | already downloaded earlier |
| `[TIME]` | no valid PDF within the timeout |
| `[WAIT]` | Telegram rate limit hit; the tool waited |
| `[ERR]` | Telegram or file-system error |

In the output folder:

- `10.1021_jp400894v.pdf`: one PDF per DOI, `/` and odd characters replaced by `_`.
- `downloads.sqlite3`: latest status of every DOI ever requested.
- `download_report.csv`: the same table, rewritten at the end of each run.
- `doi_paper_downloader.log`: debug log.

A PDF is accepted only if the attachment is a PDF by type or file name and
starts with the `%PDF-` signature. Only messages that arrive after the request
are examined, so an old attachment cannot be mistaken for the answer.

Re-running the same command resumes a batch: DOIs already downloaded are
skipped, everything else (timeouts, errors) is requested again.

Exit status: `0` all DOIs downloaded or skipped, `1` at least one failed,
`2` bad configuration or input, `130` interrupted.

## When something goes wrong

- **`Missing configuration: ...`**: no `.env` was found from the current
  folder. Run from the folder that holds it or pass `--env-file`.
- **Every DOI times out**: the bot answered with text instead of a PDF (it
  does not know the paper, or wants another message format, or sends a link).
  Run with `-v` and read the `reply without PDF:` lines in the log. Raise
  `RESPONSE_TIMEOUT` if the bot is just slow.
- **Login prompt appears again**: the `.session` file was not found. It lives
  next to the `.env` file (name set by `TG_SESSION`).
- **`[WAIT]` lines**: Telegram throttles bursts. Raise `PAUSE_BETWEEN_DOIS`
  and avoid sending hundreds of DOIs at once.
- **`cannot resolve TG_TARGET`**: open the bot or chat
  once in your Telegram app so the account knows it, and check the spelling.

Limitations: the bot is assumed to answer with a PDF attachment, never a link
(links are deliberately not followed); the message sent is the bare DOI. If
your bot needs a command or another format, change the `send_message` call in
[fetcher.py](doi_paper_downloader/fetcher.py).

## Use from Claude Code

The repository ships a Claude Code skill that lets Claude fetch papers for you
with this tool: [.claude/skills/telegram-scihub-downloader](.claude/skills/telegram-scihub-downloader/SKILL.md).
Link it once with
`ln -s "$PWD/.claude/skills/telegram-scihub-downloader" ~/.claude/skills/`.

## Package layout

| Module | Role |
| --- | --- |
| [cli.py](doi_paper_downloader/cli.py) | arguments, logging, exit codes |
| [config.py](doi_paper_downloader/config.py) | settings from `.env` / environment |
| [dois.py](doi_paper_downloader/dois.py) | DOI parsing and file names |
| [fetcher.py](doi_paper_downloader/fetcher.py) | Telegram conversation and PDF validation |
| [store.py](doi_paper_downloader/store.py) | SQLite status table and CSV report |

## Tests

```bash
pytest
```

All tests run offline (the Telegram client is replaced by a fake); none needs
credentials.

## License

[MIT](LICENSE).
