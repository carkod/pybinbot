"""Stored CVD observations returned directly by the binbot charts endpoints."""

from pydantic import AwareDatetime, BaseModel, FiniteFloat


class CvdPoint(BaseModel):
    timestamp: AwareDatetime
    buy: FiniteFloat | None
    sell: FiniteFloat | None
    cvd: FiniteFloat | None
    expected_symbols: int | None
    covered_symbols: int
    observed_minutes: int
    complete: bool
    gap: bool
    current: bool
    universe_changed: bool


class CvdAggregateResponse(BaseModel):
    source: str
    data: list[CvdPoint]
    reset_at: AwareDatetime
    updated_at: AwareDatetime | None
    stale: bool
    partial: bool


class CvdSymbolResponse(CvdAggregateResponse):
    symbol: str
