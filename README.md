# PyBinbot

Utility functions for the binbot project. Most of the code here is not runnable, there's no server or individual scripts, you simply move code to here when it's used in both binbot and binquant.

``pybinbot`` is the public API module for the distribution.

This module re-exports the internal ``shared`` and ``models`` packages and the most commonly used helpers and enums so consumers can simply::

        from pybinbot import round_numbers, ExchangeId

The implementation deliberately avoids importing heavy third-party libraries at module import time.


## Installation

```bash
uv sync --extra dev
```

`--extra dev` also installs development tools like ruff and mypy


## Publishing

1. Save your changes and do the usual Git flow (add, commit, don't push the changes yet).
2. Bump the version, choose one of these:

```bash
make bump-patch
```
or 

```bash
make bump-minor
```

or

```bash
make bump-major
```

3. Git tag the version for Github. This will read the bump version. There's a convenience command:
```
make tag
```

4. `git commit --amend`. This is to put these new changes in the previous commit so we don't dup uncessary commits. Then `git push`


For further commands take a look at the `Makefile` such as testing `make test`
