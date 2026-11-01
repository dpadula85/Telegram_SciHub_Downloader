"""dois.py - parse DOIs from text and turn them into safe file names.

A DOI is ``10.<registrant>/<suffix>``. Input lines may be bare DOIs,
``doi:`` strings or ``https://doi.org/...`` URLs; blank lines and lines
starting with ``#`` are ignored.
"""

import re
from pathlib import Path
from typing import List, Optional

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)

_URL_PREFIX_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)
_DOI_PREFIX_RE = re.compile(r"^doi:\s*", re.IGNORECASE)
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _strip_trailing_punctuation(doi: str) -> str:
    """Drop sentence punctuation and unbalanced closing parentheses.

    A trailing ")" is kept when it closes a "(" inside the DOI, as in
    ``10.1016/S0021-9258(18)00001-2``.
    """
    doi = doi.rstrip(".,;:")
    while doi.endswith(")") and doi.count(")") > doi.count("("):
        doi = doi[:-1].rstrip(".,;:")
    return doi


def normalize_doi(value: str) -> Optional[str]:
    """Return the bare DOI contained in ``value``, or None if there is none."""
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    value = _URL_PREFIX_RE.sub("", value)
    value = _DOI_PREFIX_RE.sub("", value)
    match = DOI_RE.search(value)
    if match is None:
        return None
    return _strip_trailing_punctuation(match.group(0))


def read_dois(path: Path) -> List[str]:
    """Read one DOI per line from ``path``; duplicates (case-insensitive) are dropped."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"DOI input file not found: {path}")
    found: List[str] = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        doi = normalize_doi(line)
        if doi is not None and doi.lower() not in seen:
            found.append(doi)
            seen.add(doi.lower())
    return found


def safe_filename(doi: str) -> str:
    """File-system-safe stem for ``doi`` (``/`` and other odd characters become ``_``)."""
    return _UNSAFE_RE.sub("_", doi).strip("._-")
