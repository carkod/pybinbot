from pydantic import BaseModel, Field, field_validator

from pybinbot.shared.enums import (
    BinanceKlineIntervals,
    CloseConditions,
    MarketType,
    QuoteAssets,
    Status,
    Strategy,
)
from pybinbot.shared.timestamps import timestamp, ts_to_humandate
from pybinbot.shared.types import Amount


class BotBase(BaseModel):
    pair: str
    fiat: str = Field(default="USDC")
    quote_asset: QuoteAssets = Field(default=QuoteAssets.USDC)
    fiat_order_size: Amount = Field(
        default=0, ge=0, description="Min Binance 0.0001 BNB approx 15USD"
    )
    candlestick_interval: BinanceKlineIntervals = Field(
        default=BinanceKlineIntervals.fifteen_minutes
    )
    close_condition: CloseConditions = Field(default=CloseConditions.dynamic_trailling)
    cooldown: int = Field(
        default=0,
        ge=0,
        description="cooldown period in minutes before opening next bot with same pair",
    )
    created_at: float = Field(default_factory=timestamp)
    updated_at: float = Field(default_factory=timestamp)
    dynamic_trailling: bool = Field(default=False)
    logs: list = Field(default=[])
    mode: str = Field(default="manual")
    market_type: MarketType = Field(default=MarketType.SPOT)
    name: str = Field(
        default="terminal",
        description="Algorithm name or 'terminal' if executed from React app",
    )
    status: Status = Field(default=Status.inactive)
    stop_loss: Amount = Field(
        default=0, ge=-1, le=101, description="If stop_loss > 0, allow for reversal"
    )
    margin_short_reversal: bool = Field(
        default=False,
        description="Autoswitch from long to short or short to long strategy",
    )
    take_profit: Amount = Field(default=0, ge=-1, le=101)
    trailling: bool = Field(default=False)
    trailling_deviation: Amount = Field(
        default=0,
        ge=-1,
        le=101,
        description="Trailling activation (first take profit hit)",
    )
    trailling_profit: Amount = Field(default=0, ge=-1, le=101)
    strategy: Strategy = Field(default=Strategy.long)
    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "description": "Most fields are optional. Deal and orders fields are generated internally and filled by Exchange",
            "examples": [
                {
                    "pair": "BNBUSDT",
                    "fiat": "USDC",
                    "quote_asset": "USDC",
                    "fiat_order_size": 15,
                    "candlestick_interval": "15m",
                    "close_condition": "dynamic_trailling",
                    "cooldown": 0,
                    "created_at": 1702999999.0,
                    "updated_at": 1702999999.0,
                    "dynamic_trailling": False,
                    "logs": [],
                    "mode": "manual",
                    "market_type": "SPOT",
                    "name": "Default bot",
                    "status": "inactive",
                    "stop_loss": 0,
                    "take_profit": 2.3,
                    "trailling": True,
                    "trailling_deviation": 0.63,
                    "trailling_profit": 2.3,
                    "margin_short_reversal": False,
                    "strategy": "long",
                }
            ],
        },
    }

    @field_validator("pair")
    @classmethod
    def check_pair_not_empty(cls, v):
        assert v != "", "Pair field must be filled."
        return v

    def add_log(self, message: str) -> str:
        timestamped_message = f"[{ts_to_humandate(timestamp())}] {message}"
        self.logs.append(timestamped_message)
        return self.logs[-1]
