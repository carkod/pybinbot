import enum
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch


def load_binbot_api_class():
    pybinbot_stub = types.ModuleType("pybinbot")

    class ExchangeId(enum.Enum):
        KUCOIN = "kucoin"

    class Status(enum.Enum):
        active = "active"

    pybinbot_stub.ExchangeId = ExchangeId
    pybinbot_stub.Status = Status

    handlers_stub = types.ModuleType("pybinbot.shared.handlers")
    handlers_stub.handle_binbot_errors = lambda response: response

    async def aio_response_handler(response):
        return response

    handlers_stub.aio_response_handler = aio_response_handler

    binance_stub = types.ModuleType("pybinbot.apis.binance.base")

    class BinanceApi:
        def get_ticker_price(self, symbol):
            return {"priceChangePercent": "0"}

    binance_stub.BinanceApi = BinanceApi

    module_path = (
        Path(__file__).resolve().parents[1] / "pybinbot" / "apis" / "binbot" / "base.py"
    )
    with patch.dict(
        sys.modules,
        {
            "pybinbot": pybinbot_stub,
            "pybinbot.shared.handlers": handlers_stub,
            "pybinbot.apis.binance.base": binance_stub,
        },
    ):
        spec = importlib.util.spec_from_file_location(
            "isolated_binbot_base", module_path
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module.BinbotApi


class TestSubmitBotEventLogs:
    def test_formats_string_payload(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_submit_errors = "https://example.com/bot/errors"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

        api.request = fake_request

        result = api.submit_bot_event_logs("bot-1", "failed to create bot")

        assert result == {"ok": True}
        assert captured["url"] == "https://example.com/bot/errors/bot-1"
        assert captured["method"] == "POST"
        assert captured["json"] == {"errors": "failed to create bot"}

    def test_formats_list_payload(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_submit_errors = "https://example.com/bot/errors"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

        api.request = fake_request

        result = api.submit_bot_event_logs(
            "bot-1",
            ["failed to create bot", "failed to create deal"],
        )

        assert result == {"ok": True}
        assert captured["url"] == "https://example.com/bot/errors/bot-1"
        assert captured["method"] == "POST"
        assert captured["json"] == {
            "errors": ["failed to create bot", "failed to create deal"]
        }
