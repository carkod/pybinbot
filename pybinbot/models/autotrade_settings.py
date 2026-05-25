from time import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pybinbot.models.routes import StandardResponse
from pybinbot.shared.enums import (
    AutotradeSettingsDocument,
    BinanceKlineIntervals,
    CloseConditions,
    ExchangeId,
)


class AutotradeSettingsSchema(BaseModel):
    id: AutotradeSettingsDocument = AutotradeSettingsDocument.settings
    candlestick_interval: BinanceKlineIntervals = Field(
        default=BinanceKlineIntervals.fifteen_minutes,
    )
    close_condition: CloseConditions = Field(
        default=CloseConditions.dynamic_trailing,
    )
    autotrade: bool = Field(default=False)
    updated_at: float = Field(default_factory=lambda: time() * 1000)
    # Assuming 10 USDC is the minimum, adding a bit more to avoid MIN_NOTIONAL fail.
    base_order_size: float = Field(default=15)
    trailing: bool = Field(default=False)
    trailing_deviation: float = Field(default=3)
    trailing_profit: float = Field(default=2.4)
    stop_loss: float = Field(default=0)
    take_profit: float = Field(default=2.3)
    fiat: str = Field(default="USDC")
    max_request: int = Field(default=950)
    telegram_signals: bool = Field(default=True)
    max_active_autotrade_bots: int = Field(default=1)
    autoswitch: bool = Field(default=True)
    grid_allocation_pct: float = Field(default=1.0)
    grid_cash_reserve_pct: float = Field(default=0.01)
    grid_total_margin: float = Field(default=1.0)
    grid_level_count: int = Field(default=3)
    grid_max_active_ladders: int = Field(default=3)
    max_margin_per_ladder_pct: float = Field(default=0.25)
    exchange_id: ExchangeId = Field(
        default=ExchangeId.BINANCE,
        description="Exchange where autotrade bots will operate",
    )

    model_config = ConfigDict(extra="allow", from_attributes=True, use_enum_values=True)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class AutotradeSettingsResponse(StandardResponse):
    data: AutotradeSettingsSchema


class TestAutotradeSettingsSchema(AutotradeSettingsSchema):
    id: AutotradeSettingsDocument = AutotradeSettingsDocument.test_autotrade_settings


AutotradeSettings = AutotradeSettingsSchema
