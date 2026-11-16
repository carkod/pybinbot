import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from pybinbot import BinbotApi, CvdAggregateResponse, CvdPoint, CvdSymbolResponse


def cvd_payload() -> dict:
    return {
        "source": "kucoin_futures",
        "symbol": "RUMUSDTM",
        "data": [
            {
                "timestamp": "2026-11-16T18:34:00Z",
                "buy": 245.83,
                "sell": 205.998,
                "cvd": 39.832,
                "expected_symbols": 1,
                "covered_symbols": 1,
                "observed_minutes": 1,
                "complete": True,
                "gap": False,
                "current": False,
                "universe_changed": False,
            }
        ],
        "reset_at": "2026-11-16T18:34:00Z",
        "updated_at": "2026-11-16T18:35:00Z",
        "stale": False,
        "partial": False,
    }


@pytest.fixture
def api() -> BinbotApi:
    with patch.object(BinbotApi, "_login_service_account"):
        return BinbotApi("https://example.com", "service@example.com", "password")


def test_symbol_cvd_reads_bare_snapshot_and_normalizes_contract_id(api, monkeypatch):
    fetch = AsyncMock(return_value=cvd_payload())
    monkeypatch.setattr(api, "fetch", fetch)

    result = asyncio.run(api.get_cvd_symbol("rumusdtm", limit=15))

    fetch.assert_awaited_once_with(
        url="https://example.com/charts/cvd-symbol",
        params={"symbol": "RUMUSDTM", "limit": 15},
    )
    assert isinstance(result, CvdSymbolResponse)
    assert isinstance(result.data[0], CvdPoint)
    assert result.data[0].cvd == 39.832
    assert result.updated_at == datetime(2026, 11, 16, 18, 35, tzinfo=UTC)


def test_aggregate_cvd_preserves_coverage_and_partial_observations(api, monkeypatch):
    payload = cvd_payload()
    del payload["symbol"]
    payload["partial"] = True
    payload["data"][0].update(
        buy=None,
        sell=None,
        cvd=None,
        complete=False,
        gap=True,
        expected_symbols=None,
        covered_symbols=0,
        observed_minutes=0,
    )
    fetch = AsyncMock(return_value=payload)
    monkeypatch.setattr(api, "fetch", fetch)

    result = asyncio.run(api.get_cvd_aggregate(limit=15))

    fetch.assert_awaited_once_with(
        url="https://example.com/charts/cvd-aggregate", params={"limit": 15}
    )
    assert isinstance(result, CvdAggregateResponse)
    assert result.partial is True
    assert result.data[0].cvd is None
    assert result.data[0].gap is True


@pytest.mark.parametrize("aggregate", [False, True])
def test_cvd_empty_data_is_a_valid_snapshot(api, monkeypatch, aggregate):
    payload = {**cvd_payload(), "data": [], "updated_at": None, "stale": True}
    fetch = AsyncMock(return_value=payload)
    monkeypatch.setattr(api, "fetch", fetch)
    request = api.get_cvd_aggregate() if aggregate else api.get_cvd_symbol("RUMUSDTM")

    result = asyncio.run(request)

    assert result.data == []
    assert result.updated_at is None
    assert result.stale is True
    assert fetch.await_args.kwargs["params"]["limit"] == (672 if aggregate else 15)


@pytest.mark.parametrize("aggregate", [False, True])
def test_cvd_transport_errors_propagate_without_inventing_zero_data(
    api, monkeypatch, aggregate
):
    monkeypatch.setattr(api, "fetch", AsyncMock(side_effect=TimeoutError))
    request = api.get_cvd_aggregate() if aggregate else api.get_cvd_symbol("RUMUSDTM")
    with pytest.raises(TimeoutError):
        asyncio.run(request)


@pytest.mark.parametrize("aggregate", [False, True])
def test_cvd_invalid_responses_raise_validation_errors(api, monkeypatch, aggregate):
    monkeypatch.setattr(api, "fetch", AsyncMock(return_value={"data": []}))
    request = api.get_cvd_aggregate() if aggregate else api.get_cvd_symbol("RUMUSDTM")
    with pytest.raises(ValidationError):
        asyncio.run(request)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_cvd_rejects_nonfinite_observations(invalid):
    payload = cvd_payload()
    payload["data"][0]["cvd"] = invalid
    with pytest.raises(ValidationError):
        CvdSymbolResponse.model_validate(payload)


def test_cvd_rejects_timezone_ambiguous_observation_timestamps():
    payload = cvd_payload()
    payload["data"][0]["timestamp"] = "2026-11-16T18:34:00"
    with pytest.raises(ValidationError):
        CvdSymbolResponse.model_validate(payload)
