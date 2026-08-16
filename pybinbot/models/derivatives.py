from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


OpenInterestInterval: TypeAlias = Literal[
    "5min",
    "15min",
    "30min",
    "1hour",
    "4hour",
    "1day",
]


class FuturesContractMarketData(BaseModel):
    """Normalized market data for one KuCoin futures contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    settle_currency: str | None = None
    quote_currency: str | None = None
    status: str | None = None
    source_exchanges: tuple[str, ...] = ()
    is_inverse: bool = False
    expire_date: int | None = None
    multiplier: float
    open_interest: float = Field(ge=0.0)
    mark_price: float | None = None
    index_price: float | None = None
    funding_fee_rate: float | None = None
    funding_rate_granularity: int | None = Field(default=None, gt=0)
    turnover_24h: float | None = Field(default=None, ge=0.0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class OpenInterestHistoryPoint(BaseModel):
    """One observation returned by KuCoin's UTA open-interest endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    timestamp: int = Field(alias="ts", ge=0)
    open_interest: float = Field(alias="openInterest", ge=0.0)


class OpenInterestHistoryResponse(BaseModel):
    """Validated KuCoin UTA open-interest response envelope."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    code: str
    data: list[OpenInterestHistoryPoint]

    @field_validator("code")
    @classmethod
    def validate_success_code(cls, value: str) -> str:
        if value != "200000":
            raise ValueError(f"Unexpected KuCoin response code: {value}")
        return value


class FundingRateHistoryPoint(BaseModel):
    """One settled KuCoin futures funding-rate observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str | None = None
    funding_rate: float
    timepoint: int | None = Field(default=None, ge=0)


class BinanceFundingRate(BaseModel):
    """Current funding rate from Binance's futures premium index."""

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    symbol: str
    funding_rate: float = Field(alias="lastFundingRate")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper().strip()


class BinanceFundingRatesResponse(RootModel[list[BinanceFundingRate]]):
    """Validated response from Binance's futures premium-index endpoint."""
