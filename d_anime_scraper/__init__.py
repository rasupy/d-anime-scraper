"""d-anime-scraper package root.

Public API exports:
- run_scrape, ScrapeResult
- LoginRequiredError
- __version__ (single source from version.py) (PEP 621 mirrors project.version)
"""

from .version import __version__  # noqa: F401
from .scraper import run_scrape, ScrapeResult, LoginRequiredError  # noqa: F401
