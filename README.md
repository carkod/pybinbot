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

For further commands take a look at the `Makefile` such as testing `make test`
