"""One-hour KuCoin futures rankings served by Binbot's charts API."""

from pydantic import AwareDatetime, BaseModel

from pybinbot.models.routes import StandardResponse


class FastestMoverEntry(BaseModel):
    symbol: str
    price_change_1h_percent: float
    price_change_3h_percent: float | None = None
    price_change_percent: float
    last_price: float
    turnover_24h: float


class FastestMoversSnapshot(BaseModel):
    source: str
    recorded_at: AwareDatetime | None
    comparison_at: AwareDatetime | None
    gainers: list[FastestMoverEntry]
    losers: list[FastestMoverEntry]


class FastestMoversResponse(StandardResponse):
    data: FastestMoversSnapshot
