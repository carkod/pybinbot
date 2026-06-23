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
    exchange: ExchangeId
    market_type: MarketType
    algorithm_name: str
    generated_at: datetime
    range_low: float = Field(gt=0)
    range_high: float = Field(gt=0)
    level_count: int = Field(ge=3)
    total_margin: float = Field(gt=0)
    breakout_low: float = Field(gt=0)
    breakout_high: float = Field(gt=0)
    current_price: float = Field(gt=0)
    allocation_pct: float = Field(gt=0, le=100)
    cash_reserve_pct: float = Field(ge=0, le=100)
    current_regime: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    max_margin_per_ladder: float | None = Field(default=None, gt=0)
    entry_order_type: OrderType | str | None = None
    reduce_only_take_profit: bool | None = None

    model_config = ConfigDict(
        extra="allow",
        from_attributes=True,
    )

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
    """
    Persisted grid level as returned by binbot's grid-ladder endpoints.
    Field names mirror `GridLevelTable` so clients can use this model
    to deserialize `GET /grid-ladders/{id}.detail.levels[*]`.
    """

    id: str | None = None
    ladder_id: str | None = None
    level_index: int = Field(ge=0)
    price: float = Field(gt=0)
    side: str
    contracts: int = Field(ge=0)
    margin_required: float = Field(ge=0)
    status: str
    entry_order_id: str | None = None
    take_profit_order_id: str | None = None
    filled_entry_price: float | None = None
    filled_entry_qty: float = 0
    take_profit_price: float | None = None
    realized_pnl: float = 0
    created_at: float | None = None
    updated_at: float | None = None

    model_config = ConfigDict(
        extra="allow",
        from_attributes=True,
        use_enum_values=True,
    )


class GridOrderRecord(BaseModel):
    """
    Persisted grid order as returned by binbot's grid-ladder endpoints.
    Field names mirror `GridOrderTable`.
    """

    id: str | None = None
    ladder_id: str | None = None
    level_id: str | None = None
    exchange_order_id: str | None = None
    client_oid: str | None = None
    order_role: str
    status: str | None = None
    side: str | None = None
    price: float | None = Field(default=None, gt=0)
    contracts: int = 0
    filled_qty: float = 0
    filled_price: float | None = None
    created_at: float | None = None
    updated_at: float | None = None

    model_config = ConfigDict(
        extra="allow",
        from_attributes=True,
        use_enum_values=True,
    )


class GridLadderRecord(BaseModel):
    """
    Persisted grid ladder as returned by binbot's grid-ladder endpoints.
    Field names mirror `GridLadderTable` (timestamps are floats, IDs are
    UUID strings) so clients can deserialize `detail` from the response.
    """

    id: str | None = None
    symbol: str
    fiat: str
    exchange: ExchangeId | str
    market_type: MarketType | str
    algorithm_name: str
    status: GridLadderStatus = GridLadderStatus.pending
    range_low: float
    range_high: float
    grid_step: float
    level_count: int
    total_margin: float
    reserved_margin: float = 0
    used_margin: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    breakout_low: float
    breakout_high: float
    created_at: float | None = None
    updated_at: float | None = None
    closed_at: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    levels: list[GridLevelRecord] = Field(default_factory=list)
    orders: list[GridOrderRecord] = Field(default_factory=list)

    model_config = ConfigDict(
        extra="allow",
        from_attributes=True,
        use_enum_values=True,
    )


class GridLadderCloseRequest(BaseModel):
    reason: str | None = "manual_close"
    cancel_open_orders: bool = True
    close_positions: bool = True
    reduce_only: bool = True
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class GridLadderResponse(BaseModel):
    detail: GridLadderRecord | None = None

    model_config = ConfigDict(extra="allow", from_attributes=True)


class GridLadderListResponse(BaseModel):
    detail: list[GridLadderRecord] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", from_attributes=True)
