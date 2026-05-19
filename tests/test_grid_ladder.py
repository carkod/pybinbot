from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pybinbot.apis.binbot.base import BinbotApi
from pybinbot.models.bot_base import BotBase
from pybinbot.models.grid_ladder import GridDeploymentRequest
from pybinbot.models.signals import SignalsConsumer


def valid_grid_payload() -> dict:
    return {
        "symbol": "BTCUSDC",
        "fiat": "USDC",
        "exchange": "kucoin",
        "market_type": "SPOT",
        "algorithm_name": "grid-test",
        "generated_at": datetime(2026, 5, 18, tzinfo=timezone.utc),
        "range_low": 90.0,
        "range_high": 110.0,
        "level_count": 5,
        "total_margin": 100.0,
        "breakout_low": 80.0,
        "breakout_high": 120.0,
        "current_price": 100.0,
        "current_regime": "range",
        "context": {"timeframe": "15m"},
        "indicators": {"rsi": 50},
    }


def test_grid_deployment_request_rejects_invalid_range() -> None:
    payload = valid_grid_payload()
    payload["range_low"] = 110.0
    payload["range_high"] = 90.0

    with pytest.raises(ValidationError, match="range_low must be less than range_high"):
        GridDeploymentRequest(**payload)


def test_grid_deployment_request_rejects_breakout_inside_range() -> None:
    payload = valid_grid_payload()
    payload["breakout_low"] = 95.0

    with pytest.raises(
        ValidationError, match="breakout_low must be less than range_low"
    ):
        GridDeploymentRequest(**payload)


def test_grid_deployment_request_accepts_valid_five_level_ladder() -> None:
    deployment = GridDeploymentRequest(**valid_grid_payload())

    assert deployment.symbol == "BTCUSDC"
    assert deployment.level_count == 5
    assert deployment.total_margin == 100.0


def test_signals_consumer_accepts_normal_bot_signal_unchanged() -> None:
    bot = BotBase(pair="BTCUSDC", fiat="USDC")

    signal = SignalsConsumer(direction="buy", bot_params=bot)

    assert signal.signal_kind == "bot"
    assert signal.bot_params is not None
    assert signal.bot_params.pair == "BTCUSDC"


def test_signals_consumer_accepts_grid_deploy_signal_with_grid_params() -> None:
    grid_params = GridDeploymentRequest(**valid_grid_payload())

    signal = SignalsConsumer(
        signal_kind="grid_deploy",
        direction="grid",
        grid_params=grid_params,
    )

    assert signal.signal_kind == "grid_deploy"
    assert signal.grid_params is not None
    assert signal.grid_params.symbol == "BTCUSDC"


@pytest.mark.asyncio
async def test_create_signal_includes_signal_kind_and_grid_params_in_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = object.__new__(BinbotApi)
    api.bb_signals_url = "https://example.com/signals"
    captured: dict = {}

    async def fake_fetch(**kwargs):
        captured.update(kwargs)
        return {"data": {"id": "signal-1"}}

    monkeypatch.setattr(api, "fetch", fake_fetch)

    result = await api.create_signal(
        algorithm_name="grid-test",
        symbol="BTCUSDC",
        generated_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        direction="grid",
        autotrade=True,
        current_regime="range",
        signal_kind="grid_deploy",
        grid_params={"symbol": "BTCUSDC"},
    )

    assert result == {"id": "signal-1"}
    assert captured["url"] == "https://example.com/signals"
    assert captured["method"] == "POST"
    assert captured["json"]["signal_kind"] == "grid_deploy"
    assert captured["json"]["grid_params"] == {"symbol": "BTCUSDC"}
    assert captured["json"]["bot_params"] == {}


@pytest.mark.asyncio
async def test_create_grid_signal_serializes_deployment_request_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = object.__new__(BinbotApi)
    deployment = GridDeploymentRequest(**valid_grid_payload())
    captured: dict = {}

    async def fake_create_signal(**kwargs):
        captured.update(kwargs)
        return {"id": "signal-1"}

    monkeypatch.setattr(api, "create_signal", fake_create_signal)

    result = await api.create_grid_signal(deployment, autotrade=True)

    assert result == {"id": "signal-1"}
    assert captured["algorithm_name"] == "grid-test"
    assert captured["symbol"] == "BTCUSDC"
    assert captured["direction"] == "grid"
    assert captured["autotrade"] is True
    assert captured["signal_kind"] == "grid_deploy"
    assert captured["bot_params"] == {}
    assert captured["grid_params"] == deployment.model_dump(mode="json")


def test_grid_ladder_client_methods_use_explicit_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = object.__new__(BinbotApi)
    api.bb_grid_ladders_url = "https://example.com/grid-ladders"
    api.bb_active_grid_ladders_url = "https://example.com/grid-ladders/active"
    calls: list[dict] = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(api, "request", fake_request)

    assert api.create_grid_ladder({"symbol": "BTCUSDC"}) == {"ok": True}
    assert api.get_grid_ladders() == {"ok": True}
    assert api.get_active_grid_ladders() == {"ok": True}
    assert api.get_grid_ladder("ladder-1") == {"ok": True}
    assert api.close_grid_ladder("ladder-1", {"reason": "test"}) == {"ok": True}

    assert calls == [
        {
            "url": "https://example.com/grid-ladders",
            "method": "POST",
            "json": {"symbol": "BTCUSDC"},
        },
        {"url": "https://example.com/grid-ladders"},
        {"url": "https://example.com/grid-ladders/active"},
        {"url": "https://example.com/grid-ladders/ladder-1"},
        {
            "url": "https://example.com/grid-ladders/ladder-1/close",
            "method": "POST",
            "json": {"reason": "test"},
        },
    ]
