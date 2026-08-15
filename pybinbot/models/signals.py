from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pybinbot.shared.enums import MarketType
from pandera.typing import Series
from pandera.pandas import DataFrameModel
from pybinbot.models.bot_base import BotBase
from pybinbot.models.grid_ladder import GridDeploymentRequest
from pybinbot.models.routes import StandardResponse


OpenInterestPositioningState: TypeAlias = Literal[
    "NEUTRAL",
    "NEW_LEVERAGE_LONG",
    "NEW_LEVERAGE_SHORT",
    "SHORT_SQUEEZE",
    "DELEVERAGING_FLUSH",
    "CASCADE_RISK",
]
OpenInterestSizingEvidence: TypeAlias = Literal[
    "MODERATELY_SUPPORTIVE",
    "STRONGLY_SUPPORTIVE",
    "MODERATELY_ADVERSE",
    "STRONGLY_ADVERSE",
]


class OpenInterestSizingDecision(BaseModel):
    """Signal-time OI margin adjustment retained as signal provenance."""

    baseline_margin: float = Field(gt=0)
    adjusted_margin: float = Field(gt=0)
    multiplier: float = Field(gt=0)
    oi_change_15m: float | None = None
    positioning_state: OpenInterestPositioningState
    evidence: OpenInterestSizingEvidence
    snapshot_timestamp: int = Field(ge=0)


class SignalCreate(BaseModel):
    """Payload accepted by the binbot signals endpoint."""

    algorithm_name: str = Field(max_length=128)
    symbol: str = Field(max_length=64)
    generated_at: datetime
    direction: str = Field(max_length=16)
    autotrade: bool = False
    current_regime: str | None = Field(default=None, max_length=32)
    context: dict[str, Any] = Field(default_factory=dict)
    bot_params: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    signal_kind: str = Field(default="bot", max_length=32)
    grid_params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class SignalModel(SignalCreate):
    """Pydantic representation of a persisted ``signals`` table row."""

    id: int | None = None


class SignalListRecord(BaseModel):
    """Signal row returned with or without the optional JSON payloads."""

    id: int
    algorithm_name: str = Field(max_length=128)
    symbol: str = Field(max_length=64)
    generated_at: datetime
    direction: str = Field(max_length=16)
    autotrade: bool = False
    current_regime: str | None = Field(default=None, max_length=32)
    signal_kind: str = Field(default="bot", max_length=32)
    context: dict[str, Any] | None = None
    bot_params: dict[str, Any] | None = None
    indicators: dict[str, Any] | None = None
    grid_params: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class SignalResponse(StandardResponse):
    data: SignalModel


class SignalListResponse(StandardResponse):
    data: list[SignalListRecord]


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
        if self.signal_kind == "grid_deploy" and self.grid_params is None:
            raise ValueError("grid_params is required when signal_kind is grid_deploy")
        if self.signal_kind == "grid_close" and self.grid_params is None:
            raise ValueError("grid_params is required when signal_kind is grid_close")
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
