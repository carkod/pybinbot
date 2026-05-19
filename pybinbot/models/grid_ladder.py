from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pybinbot.shared.enums import ExchangeId, MarketType, OrderType


class GridSignalKind(str, Enum):
    bot = "bot"
    grid_deploy = "grid_deploy"
    grid_close = "grid_close"


class GridLadderStatus(str, Enum):
    pending = "pending"
    active = "active"
    closing = "closing"
    closed = "closed"
    cancelled = "cancelled"
    error = "error"


class GridLevelStatus(str, Enum):
    pending = "pending"
    open = "open"
    filled = "filled"
    take_profit_open = "take_profit_open"
    completed = "completed"
    cancelled = "cancelled"
    error = "error"


class GridOrderRole(str, Enum):
    entry = "entry"
    take_profit = "take_profit"
    stop_loss = "stop_loss"
    close = "close"


class GridDeploymentRequest(BaseModel):
    symbol: str
    fiat: str
    exchange: ExchangeId | str
    market_type: MarketType | str
    algorithm_name: str
    generated_at: datetime
    range_low: float = Field(gt=0)
    range_high: float = Field(gt=0)
    level_count: int = Field(ge=3)
    total_margin: float = Field(gt=0)
    breakout_low: float = Field(gt=0)
    breakout_high: float = Field(gt=0)
    current_price: float = Field(gt=0)
    current_regime: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    allocation_pct: float | None = Field(default=None, gt=0, le=100)
    max_margin_per_ladder: float | None = Field(default=None, gt=0)
    cash_reserve_pct: float | None = Field(default=None, ge=0, le=100)
    entry_order_type: OrderType | str | None = None
    reduce_only_take_profit: bool | None = None

    model_config = ConfigDict(extra="allow", use_enum_values=True)

    @model_validator(mode="after")
    def validate_grid_boundaries(self) -> "GridDeploymentRequest":
        if self.range_low >= self.range_high:
            raise ValueError("range_low must be less than range_high")
        if self.breakout_low >= self.range_low:
            raise ValueError("breakout_low must be less than range_low")
        if self.breakout_high <= self.range_high:
            raise ValueError("breakout_high must be greater than range_high")
        if not self.breakout_low <= self.current_price <= self.breakout_high:
            raise ValueError("current_price must be inside or near the grid range")
        return self


class GridLevelRecord(BaseModel):
    id: str | None = None
    ladder_id: str | None = None
    level_index: int = Field(ge=0)
    price: float = Field(gt=0)
    margin: float = Field(ge=0)
    quantity: float | None = Field(default=None, ge=0)
    status: GridLevelStatus = GridLevelStatus.pending

    model_config = ConfigDict(extra="allow", use_enum_values=True)


class GridOrderRecord(BaseModel):
    id: str | None = None
    ladder_id: str | None = None
    level_id: str | None = None
    exchange_order_id: str | None = None
    role: GridOrderRole
    status: str | None = None
    side: str | None = None
    price: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="allow", use_enum_values=True)


class GridLadderRecord(BaseModel):
    id: str | None = None
    symbol: str
    fiat: str
    exchange: ExchangeId | str
    market_type: MarketType | str
    algorithm_name: str
    status: GridLadderStatus = GridLadderStatus.pending
    generated_at: datetime
    range_low: float
    range_high: float
    level_count: int
    total_margin: float
    breakout_low: float
    breakout_high: float
    current_price: float
    current_regime: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    levels: list[GridLevelRecord] = Field(default_factory=list)
    orders: list[GridOrderRecord] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="allow", use_enum_values=True)


class GridLadderCloseRequest(BaseModel):
    reason: str | None = None
    cancel_open_orders: bool = True
    close_positions: bool = True
    reduce_only: bool = True
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class GridLadderResponse(BaseModel):
    data: GridLadderRecord | None = None

    model_config = ConfigDict(extra="allow")


class GridLadderListResponse(BaseModel):
    data: list[GridLadderRecord] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")
