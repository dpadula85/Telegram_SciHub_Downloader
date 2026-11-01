"""config.py - settings read from the environment / a ``.env`` file.

Required: ``TG_API_ID``, ``TG_API_HASH`` (from https://my.telegram.org) and
``TG_TARGET`` (bot or chat that returns the PDFs). Optional: ``OUTPUT_DIR``,
``TG_SESSION``, ``RESPONSE_TIMEOUT`` (s), ``POLL_INTERVAL`` (s),
``PAUSE_BETWEEN_DOIS`` (s). Relative paths resolve against the directory of
the ``.env`` file that was loaded, or the current directory if there is none,
so a later change of working directory cannot move the session file.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from dotenv import dotenv_values, find_dotenv

REQUIRED_KEYS = ("TG_API_ID", "TG_API_HASH", "TG_TARGET")


@dataclass
class Settings:
    api_id: int
    api_hash: str
    target: str
    output_dir: Path
    session: Path
    timeout: float = 180.0
    poll_interval: float = 3.0
    pause_between_dois: float = 3.0

    def __post_init__(self) -> None:
        for name in ("timeout", "poll_interval"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")
        if self.pause_between_dois < 0:
            raise ValueError(
                f"pause_between_dois must be >= 0, got {self.pause_between_dois}"
            )

    @classmethod
    def from_mapping(cls, env: Mapping[str, str], base_dir: Path) -> "Settings":
        """Build from ``env``; relative paths resolve against ``base_dir``."""
        missing = [key for key in REQUIRED_KEYS if not env.get(key)]
        if missing:
            raise ValueError(
                "Missing configuration: " + ", ".join(missing)
                + ". Copy .env.example to .env and fill in the values."
            )
        try:
            api_id = int(env["TG_API_ID"])
        except ValueError:
            raise ValueError(f"TG_API_ID must be an integer, got {env['TG_API_ID']!r}")

        def _number(key: str, default: float) -> float:
            raw = env.get(key)
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                raise ValueError(f"{key} must be a number, got {raw!r}")

        def _resolve(key: str, default: str) -> Path:
            path = Path(env.get(key) or default).expanduser()
            return path if path.is_absolute() else (base_dir / path).resolve()

        return cls(
            api_id=api_id,
            api_hash=env["TG_API_HASH"],
            target=env["TG_TARGET"],
            output_dir=_resolve("OUTPUT_DIR", "papers"),
            session=_resolve("TG_SESSION", "doi_downloader"),
            timeout=_number("RESPONSE_TIMEOUT", 180.0),
            poll_interval=_number("POLL_INTERVAL", 3.0),
            pause_between_dois=_number("PAUSE_BETWEEN_DOIS", 3.0),
        )


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """Load settings from ``env_file`` (default: the nearest ``.env`` above the cwd).

    Variables already set in the process environment take precedence over
    the file, as with ``python-dotenv``.
    """
    if env_file is not None:
        env_file = Path(env_file).expanduser().resolve()
        if not env_file.is_file():
            raise FileNotFoundError(f"env file not found: {env_file}")
    else:
        found = find_dotenv(usecwd=True)
        env_file = Path(found).resolve() if found else None

    values = dict(dotenv_values(env_file)) if env_file else {}
    values.update({k: v for k, v in os.environ.items() if v})
    base_dir = env_file.parent if env_file else Path.cwd()
    return Settings.from_mapping(values, base_dir)
