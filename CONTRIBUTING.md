# Contributing Guide

Thanks for your interest in improving d-anime-scraper!

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
```

## Running Tests

```bash
pytest
```

## Lint & Type Check

```bash
ruff check .
ruff format .  # (optional)
mypy .

Ruff の設定は `pyproject.toml` 内 `[tool.ruff]` / `[tool.ruff.lint]` に統合されています。
```

## Versioning

Version is single-sourced in `d_anime_scraper/version.py` (mirror in `pyproject.toml`). Update both, then create a tag:

```bash
git commit -am "chore: bump version to x.y.z"
git tag vX.Y.Z
git push --tags
```

GitHub Actions will build binaries and attach them to the release.

## Pull Request Checklist

- [ ] Tests added/updated
- [ ] Lint passes (`ruff check .`)
- [ ] Type check passes (`mypy .`)
- [ ] README updated if behavior changed

## Reporting Issues

Please include:

- Python version (`python --version`)
- OS
- Steps to reproduce
- Relevant log excerpts (`run.log`, `_status.txt`)

Enjoy hacking!

## Notes on Packaging Metadata

`d_anime_scraper.egg-info/` is created when running `pip install -e .` (editable mode). It should not be committed. If it appears, you can safely delete the folder; it will be regenerated on the next editable install. For normal usage you can avoid generating it by installing without `-e` (regular wheel build / install).
