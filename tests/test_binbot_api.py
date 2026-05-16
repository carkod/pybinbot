import enum
import importlib.util
import sys
import types
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, create_model

from pybinbot.shared.enums import ExchangeId


def load_binbot_api_class():
    pybinbot_stub = types.ModuleType("pybinbot")

    class ExchangeId(enum.Enum):
        KUCOIN = "kucoin"

    class Status(enum.Enum):
        active = "active"

    pybinbot_stub.ExchangeId = ExchangeId
    pybinbot_stub.Status = Status

    models_stub = types.ModuleType("pybinbot.models")
    symbol_stub = types.ModuleType("pybinbot.models.symbol")

    class AssetIndexModel(BaseModel):
        id: str
        name: str = ""

    class SymbolModel(BaseModel):
        id: str
        created_at: int = 0
        updated_at: int = 0
        active: bool = True
        blacklist_reason: str = ""
        description: str = ""
        quote_asset: str = ""
        base_asset: str = ""
        cooldown: int = 0
        cooldown_start_ts: int = 0
        futures_leverage: int = Field(default=1, ge=1, le=3)
        asset_indices: list[AssetIndexModel] = []
        exchange_id: ExchangeId
        is_margin_trading_allowed: bool = False
        price_precision: int = 0
        qty_precision: int = 0
        min_notional: float = 0

        @classmethod
        def to_update_payload(cls, **fields):
            update_fields = {}
            for field_name, model_field in cls.model_fields.items():
                annotation = model_field.annotation
                if model_field.metadata:
                    annotation = Annotated[annotation, *model_field.metadata]
                update_fields[field_name] = (annotation | None, None)
            update_model = create_model(
                "SymbolModelUpdate",
                __config__=ConfigDict(extra="forbid"),
                **update_fields,
            )
            return update_model.model_validate(fields).model_dump(
                mode="json",
                exclude_unset=True,
                exclude_none=True,
            )

    symbol_stub.AssetIndexModel = AssetIndexModel
    symbol_stub.SymbolModel = SymbolModel

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
            "pybinbot.models": models_stub,
            "pybinbot.models.symbol": symbol_stub,
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


class TestEditSymbol:
    def test_puts_payload_to_symbol_url(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_one_symbol_url = "https://example.com/symbol"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"data": {"id": "BTCUSDTM", "futures_leverage": 2}}

        api.request = fake_request

        result = api.edit_symbol("BTCUSDTM", ExchangeId.KUCOIN, futures_leverage=2)

        assert result == {"id": "BTCUSDTM", "futures_leverage": 2}
        assert captured["url"] == "https://example.com/symbol"
        assert captured["method"] == "PUT"
        assert captured["json"] == {
            "futures_leverage": 2,
            "symbol": "BTCUSDTM",
            "exchange_id": "kucoin",
        }

    def test_validates_symbol_model_fields(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_one_symbol_url = "https://example.com/symbol"

        api.request = lambda **kwargs: {"data": kwargs["json"]}

        try:
            api.edit_symbol("BTCUSDTM", ExchangeId.KUCOIN, futures_leverage=4)
        except ValueError as exc:
            assert "less than or equal to 3" in str(exc)
        else:
            raise AssertionError("Expected invalid futures_leverage to fail")

    def test_rejects_fields_outside_edit_symbol_signature(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_one_symbol_url = "https://example.com/symbol"

        api.request = lambda **kwargs: {"data": kwargs["json"]}

        try:
            api.edit_symbol("BTCUSDTM", ExchangeId.KUCOIN, unsupported=True)
        except TypeError as exc:
            assert "unexpected keyword argument" in str(exc)
        else:
            raise AssertionError("Expected unknown edit_symbol field to fail")

    def test_allows_symbol_only_payload(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_one_symbol_url = "https://example.com/symbol"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"data": kwargs["json"]}

        api.request = fake_request

        result = api.edit_symbol("BTCUSDTM", ExchangeId.KUCOIN)

        assert result == {"symbol": "BTCUSDTM", "exchange_id": "kucoin"}
        assert captured["json"] == {"symbol": "BTCUSDTM", "exchange_id": "kucoin"}

    def test_omits_none_values_from_symbol_payload(self) -> None:
        api_class = load_binbot_api_class()
        api = object.__new__(api_class)
        api.bb_one_symbol_url = "https://example.com/symbol"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"data": kwargs["json"]}

        api.request = fake_request

        result = api.edit_symbol("BTCUSDTM", ExchangeId.KUCOIN, active=None)

        assert result == {"symbol": "BTCUSDTM", "exchange_id": "kucoin"}
        assert captured["json"] == {"symbol": "BTCUSDTM", "exchange_id": "kucoin"}
