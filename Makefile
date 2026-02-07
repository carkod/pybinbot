
.PHONY: format lint test bump-patch bump-minor bump-major _bump-version tag-version

VENV=.venv


format:
	@uv run ruff format .
	@uv run ruff check .  --fix
	@uv run mypy pybinbot tests --explicit-package-bases

lint:
	@uv run ruff check pybinbot
	@uv run mypy pybinbot tests --explicit-package-bases

test:
	@uv run python -m pytest tests/

bump-patch:
	@PART=patch $(MAKE) _bump-version
	@uv build
	@make tag

bump-minor:
	@PART=minor $(MAKE) _bump-version
	@uv build
	@make tag

bump-major:
	@PART=major $(MAKE) _bump-version
	@uv build
	@make tag

_bump-version:
	@uv run python tools/bump_version.py

tag: ## Tag the current version from pyproject.toml (no commit or push)
	@VERSION=$$(grep '^version\s*=\s*"[0-9]\+\.[0-9]\+\.[0-9]\+"' pyproject.toml | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/') ; \
		echo "Tagging v$$VERSION" ; \
		git tag "v$$VERSION"
		git push origin --tags
