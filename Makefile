
.PHONY: format lint test bump-patch bump-minor bump-major _bump-version

VENV=.venv


format:
	@uv run ruff format .

lint:
	@uv run ruff check .
	@uv run mypy .

test:
	@uv run python -m pytest tests/

bump-patch:
	@PART=patch $(MAKE) _bump-version

bump-minor:
	@PART=minor $(MAKE) _bump-version

bump-major:
	@PART=major $(MAKE) _bump-version

_bump-version:
	@uv run python tools/bump_version.py
