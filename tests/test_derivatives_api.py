from types import SimpleNamespace
from typing import Any

from pybinbot.apis.binance.base import BinanceApi
from pybinbot.apis.kucoin.futures import KucoinFutures


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

    def json(self) -> Any:
        return self.payload


def test_get_active_contracts_uses_sdk_and_returns_typed_models() -> None:
    api = object.__new__(KucoinFutures)
    api.futures_market_api = SimpleNamespace(
        get_all_symbols=lambda: SimpleNamespace(
            data=[
                SimpleNamespace(
                    symbol="XBTUSDTM",
                    settle_currency="USDT",
                    is_inverse=False,
                    expire_date=None,
                    multiplier=0.001,
                    open_interest="120",
                    mark_price=100.0,
                    index_price=99.0,
                    funding_fee_rate=0.0001,
                    funding_rate_granularity=28_800_000,
                    turnover_of24h=1_000.0,
                )
            ]
        )
    )

    contracts = api.get_active_contracts()

    assert len(contracts) == 1
    assert contracts[0].symbol == "XBTUSDTM"
    assert contracts[0].open_interest == 120.0
    assert contracts[0].turnover_24h == 1_000.0


def test_get_open_interest_history_validates_raw_uta_response(
    monkeypatch: Any,
) -> None:
    api = object.__new__(KucoinFutures)
    response = FakeResponse(
        {
            "code": "200000",
            "data": [{"ts": 1_000, "openInterest": "42.5"}],
        }
    )
    captured: dict[str, Any] = {}

    def fake_request(**kwargs: Any) -> FakeResponse:
        captured.update(kwargs)
        return response

    monkeypatch.setattr("pybinbot.apis.kucoin.futures.request", fake_request)

    history = api.get_open_interest_history(
        "XBTUSDTM",
        interval="5min",
        page_size=100,
    )

    assert response.raise_for_status_called is True
    assert captured == {
        "method": "GET",
        "url": KucoinFutures.OPEN_INTEREST_HISTORY_URL,
        "params": {
            "symbol": "XBTUSDTM",
            "interval": "5min",
            "pageSize": 100,
        },
        "timeout": 10,
    }
    assert history[0].timestamp == 1_000
    assert history[0].open_interest == 42.5


def test_get_public_funding_history_uses_sdk_and_returns_typed_models() -> None:
    api = object.__new__(KucoinFutures)
    captured: dict[str, Any] = {}

    def get_public_funding_history(request: Any) -> SimpleNamespace:
        captured["request"] = request
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    symbol="XBTUSDTM",
                    funding_rate=0.0001,
                    timepoint=2_000,
                )
            ]
        )

    api.futures_funding_fees_api = SimpleNamespace(
        get_public_funding_history=get_public_funding_history
    )

    history = api.get_public_funding_history("XBTUSDTM", 1_000, 2_000)

    assert captured["request"].symbol == "XBTUSDTM"
    assert captured["request"].from_ == 1_000
    assert captured["request"].to == 2_000
    assert history[0].funding_rate == 0.0001
    assert history[0].timepoint == 2_000


def test_get_futures_funding_rates_validates_binance_response(
    monkeypatch: Any,
) -> None:
    api = object.__new__(BinanceApi)
    monkeypatch.setattr(
        api,
        "request",
        lambda **kwargs: [{"symbol": "BTCUSDT", "lastFundingRate": "0.00005"}],
    )

    rates = api.get_futures_funding_rates()

    assert rates[0].symbol == "BTCUSDT"
    assert rates[0].funding_rate == 0.00005
