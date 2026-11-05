"""
KucoinFutures.place_futures_order is a thin wrapper over KuCoin's add-order
endpoint. It must report what KuCoin did and never invent a different order
(for example a market retry) on the caller's behalf.
"""

import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from kucoin_universal_sdk.generate.futures.order.model_add_order_req import AddOrderReq
from pybinbot import KucoinFutures, OrderStatus, OrderType


def _make_futures() -> Any:
    """Bypass KucoinFutures.__init__ to avoid SDK side effects."""
    f = object.__new__(KucoinFutures)
    f.DEFAULT_LEVERAGE = 2
    f.set_futures_margin_mode = MagicMock()
    f.futures_order_api = MagicMock()
    return f


def test_unacknowledged_order_raises_without_market_retry():
    f = _make_futures()
    f.futures_order_api.add_order.return_value = None

    with pytest.raises(RuntimeError, match="not acknowledged"):
        f.place_futures_order(
            symbol="KATUSDTM",
            side=AddOrderReq.SideEnum.BUY,
            size=150,
            price=0.00625,
            leverage=2,
        )

    f.futures_order_api.add_order.assert_called_once()


def test_stop_limit_order_sends_trigger_and_limit_price():
    """A native stop-limit carries both the trigger and the limit price."""
    f = _make_futures()
    f.futures_order_api.add_order.return_value = types.SimpleNamespace(
        order_id="ord-stop-limit"
    )
    f.retrieve_order = lambda oid: types.SimpleNamespace(
        status=types.SimpleNamespace(value="open"),
        filled_size="0",
        avg_deal_price="0",
        created_at=1000000,
        type=types.SimpleNamespace(value="limit"),
        time_in_force="GTC",
        side=types.SimpleNamespace(value="sell"),
    )

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        result = f.place_futures_order(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            size=8,
            order_type=OrderType.limit,
            price=0.02238,
            stop=AddOrderReq.StopEnum.DOWN,
            stop_price=0.02249,
            stop_price_type=AddOrderReq.StopPriceTypeEnum.MARK_PRICE,
            reduce_only=True,
            client_oid="stop-oid",
        )

    request = f.futures_order_api.add_order.call_args.args[0]
    assert request.type == AddOrderReq.TypeEnum.LIMIT
    assert request.price == "0.02238"
    assert request.stop == AddOrderReq.StopEnum.DOWN
    assert request.stop_price == "0.02249"
    assert request.reduce_only is True
    assert request.client_oid == "stop-oid"
    assert result.stop_price == 0.02249
    assert result.status == OrderStatus.NEW


def test_place_futures_order_marks_zero_fill_done_order_as_canceled_not_filled():
    """
    KuCoin's "done" status means the order's lifecycle ended, which includes
    cancellations, not just fills. A stop/conditional order that was accepted
    then cancelled before triggering must not be recorded as FILLED with a
    phantom qty=0/price=0 fill — that reads as a fake trade in the bot's
    order history and hides whether the position is actually protected.
    """
    f = _make_futures()
    f.futures_order_api.add_order.return_value = types.SimpleNamespace(
        order_id="ord-zero-fill"
    )
    f.retrieve_order = lambda oid: types.SimpleNamespace(
        status=types.SimpleNamespace(value="done"),
        filled_size="0",
        avg_deal_price="0",
        created_at=1000000,
        type=types.SimpleNamespace(value="market"),
        time_in_force="GTC",
        side=types.SimpleNamespace(value="sell"),
    )

    with patch("pybinbot.apis.kucoin.futures.sleep"):
        result = f.place_futures_order(
            symbol="FHEUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            size=8,
            order_type=OrderType.market,
            leverage=2,
            reduce_only=True,
        )

    assert result.status == OrderStatus.CANCELED
    assert result.qty == 0
