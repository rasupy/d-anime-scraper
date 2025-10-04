"""d-anime-scraper package root.

Public API exports:
- run_scrape, ScrapeResult
- LoginRequiredError
- __version__ (single source from version.py) (PEP 621 mirrors project.version)
"""

from .scraper import LoginRequiredError, ScrapeResult, run_scrape  # noqa: F401
from .version import __version__  # noqa: F401
