# PyBinbot

Utility functions for the binbot project. Most of the code here is not runnable, there's no server or individual scripts, you simply move code to here when it's used in both binbot and binquant.

``pybinbot`` is the public API module for the distribution.

This module re-exports the internal ``shared`` and ``models`` packages and the most commonly used helpers and enums so consumers can simply::

        from pybinbot import round_numbers, ExchangeId

Python 3.15 or newer is required. Pandas and NumPy use matching version pins in
pybinbot, binbot, and binquant. Import these libraries directly:

```python
import numpy as np
import pandas as pd
```


## Installation

```bash
uv sync --extra dev
```

`--extra dev` also installs development tools like ruff and mypy

## Futures order triggers

`KucoinFutures.place_futures_order()` defaults every conditional order to KuCoin's
last traded price (`stopPriceType=TP`) when `stop_price_type` is omitted or `None`.
This applies to both buy and sell orders, stop-market and stop-limit orders, and
opening and reducing orders. Explicit mark/index trigger types remain supported.
Orders without `stop` do not send a trigger-price type. Trigger levels, limit
prices, quantities, leverage, and fill handling are unchanged.

Last price can fluctuate more than mark price, but selecting it does not guarantee
the highest selling price or lowest buying price; fills depend on the order book.

`KucoinFutures.get_ticker_price(symbol)` returns the last traded contract price
from the futures ticker. The spot client exposes the same method for spot prices;
`KucoinFutures.get_mark_price(symbol)` remains available for mark prices.

## Stored CVD data

`BinbotApi` exposes the recorded KuCoin futures CVD endpoints:

```python
symbol_cvd = await api.get_cvd_symbol("RUMUSDTM", limit=15)
market_cvd = await api.get_cvd_aggregate(limit=15)
```

`CvdSymbolResponse`, `CvdAggregateResponse` and `CvdPoint` are public exports.
Symbol observations are one-minute buckets; aggregate observations are
15-minute buckets. Both are oldest first and retain the current/partial,
coverage, gap, universe or contract multiplier change, reset, and checkpoint
freshness fields. Missing values remain `None`, and empty collections remain
empty. Timestamp fields require time zones and numeric observations must be
finite. The endpoint responses are bare snapshots rather than
`StandardResponse` envelopes. Request and validation errors propagate to the
caller; a failed request never becomes a zero-valued reading.

Publish a new PyPI release before consuming these methods in binquant or
binbot, then upgrade each consumer's minimum dependency and lockfile to that
release.

## Telegram delivery

Import `TelegramDelivery` from `pybinbot.shared.telegram_delivery`. Initialization
loads the application's `.env` and reads `TELEGRAM_BOT_KEY` and `TELEGRAM_USER_ID`,
without overriding existing environment variables. Credentials may also be
passed explicitly.

Use `send_once(message)` for a synchronous attempt with a short timeout and no
retry or cooldown. Use `await send(message)` for asynchronous delivery with
rate-limit retries and optional spacing configured at initialization. Both use
HTML formatting and disable link previews. Delivery does not persist messages.
The Telegram library is installed as a dependency of pybinbot.


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
