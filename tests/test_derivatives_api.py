from types import SimpleNamespace
from typing import Any

import pytest

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
                    quote_currency="USDT",
                    status=SimpleNamespace(value="Open"),
                    source_exchanges=["kucoin", "binance"],
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
    assert contracts[0].quote_currency == "USDT"
    assert contracts[0].status == "Open"
    assert contracts[0].source_exchanges == ("kucoin", "binance")


def test_get_historical_klines_pages_deduplicates_and_sorts(
    monkeypatch: Any,
) -> None:
    api = object.__new__(KucoinFutures)
    hour_ms = 3_600_000
    calls: list[tuple[int | None, int | None]] = []

    def get_klines(
        symbol: str,
        interval: str,
        limit: int,
        start_time: int | None,
        end_time: int | None,
    ) -> list[list[int | float]]:
        assert symbol == "XBTUSDTM"
        assert interval == "1hour"
        assert limit == 3
        calls.append((start_time, end_time))
        assert start_time is not None
        assert end_time is not None
        return [
            [end_time, 1.0, 2.0, 0.5, 1.5, 10.0, end_time + hour_ms - 1],
            [start_time, 1.0, 2.0, 0.5, 1.5, 10.0, start_time + hour_ms - 1],
        ]

    monkeypatch.setattr(api, "get_klines", get_klines)

    rows = api.get_historical_klines(
        symbol=" xbtusdtm ",
        interval="1hour",
        start_time=hour_ms,
        end_time=5 * hour_ms,
        page_size=3,
    )

    assert calls == [
        (3 * hour_ms, 5 * hour_ms),
        (hour_ms, 2 * hour_ms),
    ]
    assert [row[0] for row in rows] == [
        hour_ms,
        2 * hour_ms,
        3 * hour_ms,
        5 * hour_ms,
    ]


def test_get_historical_klines_rejects_invalid_ranges() -> None:
    api = object.__new__(KucoinFutures)

    with pytest.raises(ValueError, match="start_time"):
        api.get_historical_klines("XBTUSDTM", "1hour", 2_000, 1_000)
    with pytest.raises(ValueError, match="page_size"):
        api.get_historical_klines("XBTUSDTM", "1hour", 1_000, 2_000, page_size=201)


def test_get_ui_klines_uses_historical_interface_and_applies_limit(
    monkeypatch: Any,
) -> None:
    api = object.__new__(KucoinFutures)
    hour_ms = 3_600_000
    rows = [[hour * hour_ms, 1.0, 2.0, 0.5, 1.5, 10.0, 0] for hour in range(4)]
    captured: dict[str, Any] = {}

    def get_historical_klines(**kwargs: Any) -> list[list[int | float]]:
        captured.update(kwargs)
        return rows

    monkeypatch.setattr(api, "get_historical_klines", get_historical_klines)

    result = api.get_ui_klines(
        symbol="XBTUSDTM",
        interval="1hour",
        limit=2,
        start_time=hour_ms,
        end_time=3 * hour_ms,
    )

    assert result == rows[-2:]
    assert captured == {
        "symbol": "XBTUSDTM",
        "interval": "1hour",
        "start_time": hour_ms,
        "end_time": 3 * hour_ms,
    }


def test_get_ui_klines_keeps_dashboard_endpoint_for_five_minutes(
    monkeypatch: Any,
) -> None:
    api = object.__new__(KucoinFutures)
    captured: dict[str, Any] = {}

    def dashboard_request(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": "200",
                "data": [[60, 1.0, 2.0, 0.5, 1.5, 10.0]],
            },
        )

    monkeypatch.setattr("pybinbot.apis.kucoin.futures.request", dashboard_request)
    monkeypatch.setattr(
        api,
        "get_historical_klines",
        lambda **kwargs: pytest.fail("SDK fallback should not be used"),
    )

    rows = api.get_ui_klines(
        symbol="XBTUSDTM",
        interval="5min",
        limit=1,
        start_time=60_000,
        end_time=360_000,
    )

    assert rows == [[60_000, 1.0, 2.0, 0.5, 1.5, 10.0, 359_999]]
    assert captured["params"] == {
        "type": "5min",
        "begin": 60,
        "end": 360,
        "symbol": "XBTUSDTM",
    }


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
        " xbtusdtm ",
        interval="5min",
        page_size=100,
        start_at=500,
        end_at=2_000,
    )

    assert response.raise_for_status_called is True
    assert captured == {
        "method": "GET",
        "url": KucoinFutures.OPEN_INTEREST_HISTORY_URL,
        "params": {
            "symbol": "XBTUSDTM",
            "interval": "5min",
            "pageSize": 100,
            "startAt": 500,
            "endAt": 2_000,
        },
        "timeout": 10,
    }
    assert history[0].timestamp == 1_000
    assert history[0].open_interest == 42.5


def test_get_open_interest_history_rejects_invalid_ranges() -> None:
    api = object.__new__(KucoinFutures)

    with pytest.raises(ValueError, match="page_size"):
        api.get_open_interest_history("XBTUSDTM", page_size=0)
    with pytest.raises(ValueError, match="start_at"):
        api.get_open_interest_history("XBTUSDTM", start_at=2_000, end_at=1_000)


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
