"""
Tests for the anti-wick KucoinFutures.matching_engine (reference_price path)
and the _close_with_escalation ladder.

The reference_price path prevents futures exits from filling into hollow-book
wicks.  Confirmed against the FHEUSDTM 2026-05-31 case:
  long opened 0.02343, SL 0.02249, actual fill 0.02235 (wick low).
  With reference_price=0.02252 (last closed 15m candle), cap ≈ 0.02247,
  matching_engine returns None (no bids within the cap band on the wick),
  which triggers _close_with_escalation to post an IOC at the cap price.
  When the wick bounces the IOC fills at ~0.02247 instead of 0.02235.

Key design facts:
  - matching_engine WITH reference_price returns the capped crossing price when
    the book has liquidity at or above the cap, or None when it doesn't.
  - matching_engine WITHOUT reference_price (legacy entry path) always returns
    a price (1-tick aggressive cross, no band).
  - _close_with_escalation computes the cap price directly and posts IOC steps,
    widening the band if unfilled, falling back to market for guaranteed exit.
"""

import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from kucoin_universal_sdk.generate.futures.order.model_add_order_req import AddOrderReq
from pybinbot import KucoinFutures, OrderStatus, DealType
from pybinbot.models.order import OrderBase
from pybinbot.shared.maths import round_numbers

_EXIT_MAX_SLIPPAGE_PCT = KucoinFutures._EXIT_MAX_SLIPPAGE_PCT
_EXIT_ESCALATION_STEP_PCT = KucoinFutures._EXIT_ESCALATION_STEP_PCT
_EXIT_MAX_SLIPPAGE_HARD_PCT = KucoinFutures._EXIT_MAX_SLIPPAGE_HARD_PCT


# FHEUSDTM production values: tick_size=0.00001 → precision=5
FHEU_TICK = 0.00001
FHEU_PREC = 5


def _make_futures(tick_size: float = FHEU_TICK, precision: int = FHEU_PREC) -> Any:
    """Bypass KucoinFutures.__init__ to avoid SDK side effects."""
    f = object.__new__(KucoinFutures)
    f._tick_size = MagicMock(return_value=tick_size)  # type: ignore[method-assign]
    f._calculate_price_precision = MagicMock(return_value=precision)  # type: ignore[method-assign]
    return f


def _mock_book(bids, asks):
    return types.SimpleNamespace(bids=bids, asks=asks)


def _order_base(
    order_id: str,
    price: float,
    filled: float,
    side: str = "sell",
) -> OrderBase:
    return OrderBase(
        order_id=order_id,
        order_type="limit",
        pair="FHEUSDTM",
        timestamp=1000000,
        order_side=side,
        qty=filled,
        price=price,
        status=OrderStatus.FILLED if filled > 0 else OrderStatus.NEW,
        time_in_force="IOC",
        deal_type=DealType.base_order,
    )


# ---------------------------------------------------------------------------
# matching_engine — legacy path (no reference_price)
# ---------------------------------------------------------------------------


def test_legacy_path_buy_crosses_spread_by_one_tick():
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02340", "100"]],
        asks=[["0.02350", "100"]],
    )
    # BUY legacy: best_ask + tick = 0.02350 + 0.00001 = 0.02351
    result = f.matching_engine("FHEUSDTM", size=8, side=AddOrderReq.SideEnum.BUY)
    assert result == pytest.approx(0.02351, abs=1e-6)


def test_legacy_path_sell_crosses_spread_by_one_tick():
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02340", "100"]],
        asks=[["0.02350", "100"]],
    )
    # SELL legacy: best_bid - tick = 0.02340 - 0.00001 = 0.02339
    result = f.matching_engine("FHEUSDTM", size=8, side=AddOrderReq.SideEnum.SELL)
    assert result == pytest.approx(0.02339, abs=1e-6)


# ---------------------------------------------------------------------------
# matching_engine — anti-wick path (reference_price provided)
# ---------------------------------------------------------------------------


def test_sell_wick_book_returns_none():
    """
    FHEUSDTM wick scenario: top bid = 0.02235 (the wick low), below the cap.
    reference_price = 0.02252, cap = 0.02252 * 0.998 ≈ 0.02247.
    A limit SELL at 0.02247 cannot fill against a bid of 0.02235 (bid too low).
    matching_engine returns None → escalation ladder handles it.
    """
    f = _make_futures()
    f.futures_market_api = MagicMock()
    # All bids are below the cap (0.02247)
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02235", "50"], ["0.02200", "50"]],
        asks=[["0.02260", "50"]],
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.SELL,
        reference_price=0.02252,
    )
    assert result is None, (
        "Wick book has no bids within the cap band — should return None"
    )


def test_sell_normal_book_returns_capped_crossing():
    """
    Normal book: best bid 0.02248, above cap 0.02247.
    Crossing = 0.02248 - tick = 0.02247.  Cap = 0.02247.  Clamped = 0.02247.
    Book walk succeeds (0.02248 >= cap) → return capped price.
    """
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02248", "50"]],
        asks=[["0.02260", "50"]],
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.SELL,
        reference_price=0.02252,
    )
    # cap = floor(0.02252 * 0.998, 5) = floor(0.02247496, 5) = 0.02247
    expected = round_numbers(0.02252 * (1.0 - _EXIT_MAX_SLIPPAGE_PCT), FHEU_PREC)
    assert result == pytest.approx(expected, abs=1e-6)


def test_sell_returns_none_when_all_bids_below_cap():
    """All bids below cap → None."""
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02230", "100"]],
        asks=[["0.02260", "50"]],
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.SELL,
        reference_price=0.02252,
    )
    assert result is None


def test_buy_wick_book_returns_none():
    """
    BUY mirror: spike pushed top ask to 0.02280 (above cap 0.02257).
    A limit BUY at cap cannot fill against an ask of 0.02280 → None.
    """
    f = _make_futures()
    f.futures_market_api = MagicMock()
    # All asks are above the BUY cap
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02250", "50"]],
        asks=[["0.02280", "100"]],
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.BUY,
        reference_price=0.02252,
    )
    assert result is None


def test_buy_normal_book_returns_capped_crossing():
    """
    Normal book: best ask 0.02253, below BUY cap 0.02257.
    Returns the crossing price (ask + tick = 0.02254, within cap) capped down.
    """
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02250", "50"]],
        asks=[["0.02253", "50"]],  # below cap
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.BUY,
        reference_price=0.02252,
    )
    # BUY cap = 0.02252 * 1.002 = 0.02256504, crossing = 0.02253 + tick = 0.02254
    # clamped = min(0.02254, 0.02256504) = 0.02254, within band → fill
    assert result is not None
    assert result <= 0.02252 * (1.0 + _EXIT_MAX_SLIPPAGE_PCT) + 1e-6


def test_empty_levels_returns_none():
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(bids=[], asks=[])
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.SELL,
        reference_price=0.02252,
    )
    assert result is None


def test_sell_insufficient_size_returns_none():
    """Book has bids in-band but total qty < size → None."""
    f = _make_futures()
    f.futures_market_api = MagicMock()
    f.futures_market_api.get_full_order_book.return_value = _mock_book(
        bids=[["0.02248", "3"]],  # only 3 contracts in-band, need 8
        asks=[["0.02260", "50"]],
    )
    result = f.matching_engine(
        "FHEUSDTM",
        size=8,
        side=AddOrderReq.SideEnum.SELL,
        reference_price=0.02252,
    )
    assert result is None


# ---------------------------------------------------------------------------
# _close_with_escalation — step behaviour and market fallback
# ---------------------------------------------------------------------------


def test_escalation_fills_on_first_ioc_step():
    """IOC step-0 fills fully — no further steps or market order needed."""
    f = _make_futures()
    placed_orders: list[dict] = []

    def fake_place(**kwargs) -> OrderBase:
        placed_orders.append(dict(kwargs))
        return _order_base("ord-1", kwargs.get("price", 0.0), 8)

    def fake_retrieve(order_id: str):
        return types.SimpleNamespace(filled_size="8", avg_deal_price="0.02247")

    f.place_futures_order = fake_place
    f.retrieve_order = fake_retrieve

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        f._close_with_escalation(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            qty=8,
            leverage=2,
            reference_price=0.02252,
        )

    assert len(placed_orders) == 1
    o = placed_orders[0]
    # order_type is the internal OrderType enum; value is 'LIMIT'
    from pybinbot import OrderType

    assert o["order_type"] == OrderType.limit
    assert o["time_in_force"] == AddOrderReq.TimeInForceEnum.IMMEDIATE_OR_CANCEL
    assert o["reduce_only"] is True
    # Price should be at the slippage cap
    expected = round_numbers(0.02252 * (1.0 - _EXIT_MAX_SLIPPAGE_PCT), FHEU_PREC)
    assert o["price"] == pytest.approx(expected, abs=1e-5)


def test_escalation_widens_cap_each_step_then_market_fallback():
    """
    Steps 0..MAX_STEPS all return unfilled (filled_size=0) → final fallback
    must be a plain market order.
    """
    f = _make_futures()
    placed_orders: list[dict] = []

    def fake_place(**kwargs) -> OrderBase:
        placed_orders.append(dict(kwargs))
        oid = f"ord-{len(placed_orders)}"
        return _order_base(oid, kwargs.get("price", 0.0), 0)

    def fake_retrieve(order_id: str):
        return types.SimpleNamespace(filled_size="0", avg_deal_price="0")

    f.place_futures_order = fake_place
    f.retrieve_order = fake_retrieve

    from pybinbot import OrderType

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        f._close_with_escalation(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            qty=8,
            leverage=2,
            reference_price=0.02252,
        )

    # Total calls = (MAX_STEPS+1) IOC limit steps + 1 market fallback
    import math

    expected_limit_steps = (
        math.floor(
            (_EXIT_MAX_SLIPPAGE_HARD_PCT - _EXIT_MAX_SLIPPAGE_PCT)
            / _EXIT_ESCALATION_STEP_PCT
        )
        + 1
    )
    # Total = limit steps + 1 market fallback
    assert len(placed_orders) == expected_limit_steps + 1

    # Each limit step should have a lower price than the previous (wider cap for SELL)
    limit_orders = placed_orders[:expected_limit_steps]
    limit_prices = [o["price"] for o in limit_orders]
    for i in range(1, len(limit_prices)):
        assert limit_prices[i] < limit_prices[i - 1], (
            f"Step {i} price {limit_prices[i]} should be lower than step {i - 1} price {limit_prices[i - 1]}"
        )

    # Final order must be market (no price set, or order_type is market)
    final = placed_orders[-1]
    assert final.get("order_type") == OrderType.market


def test_escalation_partial_fill_reduces_remaining_qty():
    """
    Step 0 fills 5 of 8 contracts; step 1 fills the remaining 3.
    Only 2 limit orders placed, no market fallback.
    """
    f = _make_futures()
    placed_orders: list[dict] = []
    fills = [5, 3]
    retrieve_calls: list[int] = [0]

    def fake_place(**kwargs) -> OrderBase:
        placed_orders.append(dict(kwargs))
        oid = f"ord-{len(placed_orders)}"
        return _order_base(oid, kwargs.get("price", 0.0), 0)

    def fake_retrieve(order_id: str):
        idx = retrieve_calls[0]
        retrieve_calls[0] += 1
        fill = fills[min(idx, len(fills) - 1)]
        return types.SimpleNamespace(
            filled_size=str(fill),
            avg_deal_price="0.02247",
        )

    f.place_futures_order = fake_place
    f.retrieve_order = fake_retrieve

    from pybinbot import OrderType

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        f._close_with_escalation(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            qty=8,
            leverage=2,
            reference_price=0.02252,
        )

    # 2 steps filled 5+3=8, no market fallback needed
    assert len(placed_orders) == 2
    for o in placed_orders:
        assert o.get("order_type") != OrderType.market


def test_escalation_reduce_only_preserved_on_every_step():
    """reduce_only=True must be set on every placed order including the final market."""
    f = _make_futures()
    placed_orders: list[dict] = []

    def fake_place(**kwargs) -> OrderBase:
        placed_orders.append(dict(kwargs))
        return _order_base(f"ord-{len(placed_orders)}", kwargs.get("price", 0.0), 0)

    f.place_futures_order = fake_place
    f.retrieve_order = lambda oid: types.SimpleNamespace(
        filled_size="0", avg_deal_price="0"
    )

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        f._close_with_escalation(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            qty=8,
            leverage=2,
            reference_price=0.02252,
            reduce_only=True,
        )

    assert len(placed_orders) > 0
    assert all(o["reduce_only"] is True for o in placed_orders)
