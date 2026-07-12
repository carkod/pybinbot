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
