from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    message: str
    error: int = Field(default=0)


class MarketBreadthSeries(BaseModel):
    """Market-breadth parallel arrays returned newest-first by binbot."""

    timestamp: list[str]
    advancers: list[int]
    decliners: list[int]
    market_breadth: list[float]
    market_breadth_ma: list[float | None]
    avg_gain: list[float]
    avg_loss: list[float]
    total_volume: list[float]
    strength_index: list[float]


class MarketBreadthSeriesResponse(StandardResponse):
    data: MarketBreadthSeries


class GainerLoserEntry(BaseModel):
    """One symbol's 24h move inside a gainers/losers snapshot."""

    symbol: str
    price_change_percent: float


class GainersLosersSnapshot(BaseModel):
    """
    A single top-gainers/top-losers snapshot recorded by binbot.

    `recorded_at` is an ISO-8601 timestamp string as stored by binbot.
    """

    source: str
    recorded_at: str
    top_gainers: list[GainerLoserEntry]
    top_losers: list[GainerLoserEntry]


class GainersLosersSeriesResponse(StandardResponse):
    """Snapshots are returned newest-first by binbot."""

    data: list[GainersLosersSnapshot]
