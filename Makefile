
.PHONY: format lint test bump-patch bump-minor bump-major _bump-version _git-release

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
	@$(MAKE) _git-release

bump-minor:
	@uv build
	@PART=minor $(MAKE) _bump-version
	@$(MAKE) _git-release

bump-major:
	@uv build
	@PART=major $(MAKE) _bump-version
	@$(MAKE) _git-release

_bump-version:
	@uv run python tools/bump_version.py

_git-release:
	@VERSION=$$(grep '^version\s*=\s*"[0-9]\+\.[0-9]\+\.[0-9]\+"' pyproject.toml | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/') ; \
		echo "Committing and tagging v$$VERSION" ; \
		git add pyproject.toml ; \
		git commit -m "Bump version to $$VERSION" ; \
		git tag "v$$VERSION" ; \
		git push origin HEAD ; \
		git push origin "v$$VERSION"
