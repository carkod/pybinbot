from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pybinbot.shared.enums import MarketType
from pandera.typing import Series
from pandera.pandas import DataFrameModel
from pybinbot.models.bot_base import BotBase
from pybinbot.models.grid_ladder import GridDeploymentRequest


class HABollinguerSpread(BaseModel):
    """
    Pydantic model for the Bollinguer spread.
    """

    bb_high: float
    bb_mid: float
    bb_low: float


class SignalsConsumer(BaseModel):
    """
    Pydantic model for the signals consumer.
    """

    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    direction: str = Field(default="", description="Signal direction: buy/sell")
    score: float = Field(default=0, description="Score for ranking signals")
    spread: float = Field(default=0)
    current_price: float = Field(default=0)
    bb_spreads: HABollinguerSpread | None = Field(default=None)
    autotrade: bool = Field(default=True, description="If it is in testing mode, False")
    signal_kind: Literal["bot", "grid_deploy", "grid_close"] = Field(
        default="bot", description="Signal envelope kind"
    )
    bot_params: BotBase | None = Field(
        default=None, description="Parameters for bot creation"
    )
    grid_params: GridDeploymentRequest | None = Field(
        default=None, description="Parameters for grid ladder deployment"
    )

    model_config = ConfigDict(
        extra="allow",
        use_enum_values=True,
    )

    @model_validator(mode="after")
    def validate_signal_payload(self) -> "SignalsConsumer":
        if self.signal_kind == "bot" and self.bot_params is None:
            raise ValueError("bot_params is required when signal_kind is bot")
        if self.signal_kind == "grid_deploy" and self.grid_params is None:
            raise ValueError("grid_params is required when signal_kind is grid_deploy")
        return self

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
    market_type: MarketType | None = Field(default=None)


class KlineSchema(DataFrameModel):
    open: Series[float]
    high: Series[float]
    low: Series[float]
    close: Series[float]
    volume: Series[float]

    class Config:
        strict = False
