from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pybinbot.shared.enums import MarketType, Strategy


class HABollinguerSpread(BaseModel):
    """Pydantic model for the Bollinguer spread."""

    bb_high: float
    bb_mid: float
    bb_low: float


class SignalsConsumer(BaseModel):
    """Pydantic model for the signals consumer."""

    type: str = Field(default="signal")
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    spread: float = Field(default=0)
    current_price: float = Field(default=0)
    msg: str = Field(
        description="Message to be sent to Telegram, written in HTML string"
    )
    symbol: str
    algo: str = Field(description="Algorithm name generating the signal")
    bot_strategy: Strategy = Field(default=Strategy.long)
    bb_spreads: HABollinguerSpread | None = Field(default=None)
    autotrade: bool = Field(default=True, description="If it is in testing mode, False")
    market_type: MarketType = Field(
        default=MarketType.SPOT, description="spot or futures"
    )

    model_config = ConfigDict(
        extra="allow",
        use_enum_values=True,
    )

    @field_validator("spread", "current_price")
    @classmethod
    def name_must_contain_space(cls, v):
        if v is None:
            return 0
        elif isinstance(v, str):
            return float(v)
        elif isinstance(v, float):
            return v
        else:
            raise ValueError("must be a float or 0")


class SingleCandle(BaseModel):
    """
    Pydantic model for a single candle.
    """

    symbol: str
    open_time: int = Field()
    close_time: int
    open_price: float
    close_price: float
    high_price: float
    low_price: float
    volume: float

    @field_validator("open_time", "close_time")
    @classmethod
    def validate_time(cls, v):
        if v is None:
            return 0
        elif isinstance(v, str):
            return int(v)
        elif isinstance(v, int):
            return v
        else:
            raise ValueError("must be a int or 0")

    @field_validator("open_price", "close_price", "high_price", "low_price", "volume")
    @classmethod
    def validate_price(cls, v):
        if v is None:
            return 0
        elif isinstance(v, str):
            return float(v)
        elif isinstance(v, float):
            return v
        else:
            raise ValueError("must be a float or 0")


class KlineProduceModel(BaseModel):
    symbol: str
    open_time: str
    close_time: str
    open_price: str
    close_price: str
    high_price: str
    low_price: str
    volume: float
