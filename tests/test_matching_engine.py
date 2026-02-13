import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from pybinbot import KucoinOrders


def mock_order_book(bids, asks):
    return SimpleNamespace(bids=bids, asks=asks)


@pytest.fixture
def kucoin_orders():
    # Bypass KucoinOrders.__init__ so tests avoid SDK side effects.
    return object.__new__(KucoinOrders)


def test_matching_engine_buy_order(kucoin_orders):
    bids = [["100.0", "2"], ["99.5", "3"]]
    asks = [["101.0", "1"], ["102.0", "2"]]
    kucoin_orders.get_full_order_book = MagicMock(
        return_value=mock_order_book(bids, asks)
    )

    result = kucoin_orders.matching_engine("BTC-USDT", order_side=False, base_qty=2)

    assert result == 100.0


def test_matching_engine_sell_order(kucoin_orders):
    bids = [["100.0", "2"], ["99.5", "3"]]
    asks = [["101.0", "1"], ["102.0", "2"]]
    kucoin_orders.get_full_order_book = MagicMock(
        return_value=mock_order_book(bids, asks)
    )

    result = kucoin_orders.matching_engine("BTC-USDT", order_side=True, base_qty=2)

    assert result == 102.0


def test_matching_engine_insufficient_liquidity(kucoin_orders):
    bids = [["100.0", "1"]]
    asks = [["101.0", "1"]]
    kucoin_orders.get_full_order_book = MagicMock(
        return_value=mock_order_book(bids, asks)
    )

    result_buy = kucoin_orders.matching_engine("BTC-USDT", order_side=False, base_qty=2)
    result_sell = kucoin_orders.matching_engine("BTC-USDT", order_side=True, base_qty=2)

    assert result_buy is None
    assert result_sell is None


def test_matching_engine_slippage_cap(kucoin_orders):
    bids = [["100.0", "1"], ["98.0", "2"]]
    # Asks intentionally ordered high-to-low to mirror KuCoin response ordering
    asks = [["104.0", "2"], ["101.0", "1"]]
    kucoin_orders.get_full_order_book = MagicMock(
        return_value=mock_order_book(bids, asks)
    )

    result_buy = kucoin_orders.matching_engine("BTC-USDT", order_side=False, base_qty=3)
    result_sell = kucoin_orders.matching_engine("BTC-USDT", order_side=True, base_qty=3)

    assert result_buy == 98.0
    assert result_sell is None
