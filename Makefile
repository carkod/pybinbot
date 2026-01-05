
.PHONY: format lint test bump-patch bump-minor bump-major _bump-version tag-version

VENV=.venv


format:
	@uv run ruff format .

lint:
	@uv run ruff check .
	@uv run mypy .

test:
	@uv run python -m pytest tests/

bump-patch:
	@uv build
	@PART=patch $(MAKE) _bump-version

bump-minor:
	@uv build
	@PART=minor $(MAKE) _bump-version

bump-major:
	@uv build
	@PART=major $(MAKE) _bump-version

_bump-version:
	@uv run python tools/bump_version.py

tag: ## Tag the current version from pyproject.toml (no commit or push)
	@VERSION=$$(grep '^version\s*=\s*"[0-9]\+\.[0-9]\+\.[0-9]\+"' pyproject.toml | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/') ; \
		echo "Tagging v$$VERSION" ; \
		git tag "v$$VERSION"
