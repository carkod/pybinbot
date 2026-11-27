from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from pybinbot import BinbotApi, FastestMoversSnapshot


@pytest.fixture
def api() -> BinbotApi:
    with patch.object(BinbotApi, "_login_service_account"):
        return BinbotApi("https://example.com", "service@example.com", "password")


@pytest.mark.asyncio
async def test_fastest_movers_client_returns_typed_rankings_and_context(api: BinbotApi):
    payload = {
        "source": "kucoin_futures",
        "recorded_at": "2026-11-27T12:00:00Z",
        "comparison_at": "2026-11-27T11:00:00Z",
        "gainers": [
            {
                "symbol": "SOLUSDTM",
                "price_change_1h_percent": 4.2,
                "price_change_3h_percent": 7.8,
                "price_change_percent": 12.1,
                "last_price": 150,
                "turnover_24h": 1000000,
            }
        ],
        "losers": [],
    }
    with patch.object(
        api, "fetch", new=AsyncMock(return_value={"message": "OK", "data": payload})
    ) as fetch:
        snapshot = await api.get_fastest_movers(limit=5)

    fetch.assert_awaited_once_with(
        url="https://example.com/charts/fastest_movers", params={"limit": 5}
    )
    assert isinstance(snapshot, FastestMoversSnapshot)
    assert snapshot.recorded_at == datetime(2026, 11, 27, 12, tzinfo=UTC)
    assert snapshot.gainers[0].price_change_3h_percent == 7.8
    assert snapshot.gainers[0].price_change_percent == 12.1


@pytest.mark.asyncio
async def test_fastest_movers_preserves_waiting_for_history_state(api: BinbotApi):
    with patch.object(
        api,
        "fetch",
        new=AsyncMock(
            return_value={
                "message": "OK",
                "data": {
                    "source": "kucoin_futures",
                    "recorded_at": None,
                    "comparison_at": None,
                    "gainers": [],
                    "losers": [],
                },
            }
        ),
    ):
        snapshot = await api.get_fastest_movers()
    assert snapshot.recorded_at is None
    assert snapshot.comparison_at is None
    assert snapshot.gainers == []


@pytest.mark.asyncio
async def test_fastest_movers_does_not_turn_api_failure_into_empty_membership(
    api: BinbotApi,
):
    with patch.object(api, "fetch", new=AsyncMock(return_value={"data": None})):
        with pytest.raises(ValidationError):
            await api.get_fastest_movers()


def test_fastest_movers_rejects_ambiguous_snapshot_timezone():
    with pytest.raises(ValidationError):
        FastestMoversSnapshot(
            source="kucoin_futures",
            recorded_at=datetime(2026, 11, 27, 12),
            comparison_at=None,
            gainers=[],
            losers=[],
        )
