from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pybinbot.apis.kucoin.base import KucoinApi
from pybinbot.apis.kucoin.futures import KucoinFutures


def test_get_ticker_price_raises_clear_error_when_price_is_missing():
    api = object.__new__(KucoinApi)
    api.spot_api = SimpleNamespace(
        get_ticker=lambda request: SimpleNamespace(price=None, reason="missing ticker")
    )

    with pytest.raises(
        ValueError, match="KuCoin spot ticker returned no price for HOMEUSDTM"
    ):
        api.get_ticker_price("HOMEUSDTM")


def test_get_ticker_price_returns_float_when_price_is_available():
    api = object.__new__(KucoinApi)
    api.spot_api = SimpleNamespace(
        get_ticker=lambda request: SimpleNamespace(price="12.34")
    )

    assert api.get_ticker_price("BTC-USDT") == 12.34


def test_futures_ticker_returns_last_trade_instead_of_spot_mark_or_book():
    api = object.__new__(KucoinFutures)
    ticker = Mock(
        return_value=SimpleNamespace(
            price="101.5", best_bid_price="101", best_ask_price="102"
        )
    )
    api.futures_market_api = SimpleNamespace(
        get_ticker=ticker, get_mark_price=Mock(return_value=100)
    )
    spot_ticker = Mock(return_value=SimpleNamespace(price="99"))
    api.spot_api = SimpleNamespace(get_ticker=spot_ticker)

    assert api.get_ticker_price("XBTUSDTM") == 101.5

    ticker.assert_called_once()
    assert ticker.call_args.args[0].symbol == "XBTUSDTM"
    api.futures_market_api.get_mark_price.assert_not_called()
    spot_ticker.assert_not_called()


def test_futures_ticker_raises_clear_error_when_response_is_missing():
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(get_ticker=Mock(return_value=None))

    with pytest.raises(ValueError, match="KuCoin futures ticker returned no response"):
        api.get_ticker_price("XBTUSDTM")


def test_futures_ticker_raises_clear_error_when_price_is_missing():
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(
        get_ticker=Mock(return_value=SimpleNamespace(price=None))
    )

    with pytest.raises(ValueError, match="KuCoin futures ticker returned no price"):
        api.get_ticker_price("XBTUSDTM")


@pytest.mark.parametrize("price", ["0", "-1", "nan", "inf", "invalid"])
def test_futures_ticker_rejects_invalid_last_trade_prices(price):
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(
        get_ticker=Mock(return_value=SimpleNamespace(price=price))
    )

    with pytest.raises(ValueError):
        api.get_ticker_price("XBTUSDTM")


def test_get_mark_price_raises_clear_error_when_value_is_missing():
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(
        get_mark_price=lambda request: SimpleNamespace(
            value=None, reason="missing mark"
        )
    )

    with pytest.raises(
        ValueError, match="KuCoin futures mark price returned no value for HOMEUSDTM"
    ):
        api.get_mark_price("HOMEUSDTM")


def test_get_mark_price_returns_float_when_value_is_available():
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(
        get_mark_price=lambda request: SimpleNamespace(value="12.34")
    )

    assert api.get_mark_price("BTCUSDTM") == 12.34


def test_cancel_futures_order_uses_standard_order_cancel_by_id():
    api = object.__new__(KucoinFutures)
    captured = {}
    expected = SimpleNamespace(order_id="entry-order-1")

    def cancel_order_by_id(request):
        captured["request"] = request
        return expected

    api.futures_order_api = SimpleNamespace(cancel_order_by_id=cancel_order_by_id)

    result = api.cancel_futures_order("entry-order-1")

    assert result is expected
    assert captured["request"].order_id == "entry-order-1"
