"""Allow ``python -m doi_paper_downloader``."""

import sys

from .cli import main

sys.exit(main())
