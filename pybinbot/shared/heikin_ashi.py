from typing import cast

from pandas import DataFrame, concat
from pandas.api.types import is_numeric_dtype
from pandas import to_numeric
from pandera.typing import DataFrame as TypedDataFrame
from pybinbot.models.signals import KlineSchema
from pybinbot.shared.enums import ExchangeId
from pybinbot.shared.candles import Candles


class HeikinAshi(Candles):
    """
    Heikin Ashi candle transformation built on top of ``Candles``.

    Canonical formulas applied to OHLC data:
        HA_Close = (O + H + L + C) / 4
        HA_Open  = (prev_HA_Open + prev_HA_Close) / 2, seed = (O0 + C0) / 2
        HA_High  = max(H, HA_Open, HA_Close)
        HA_Low   = min(L, HA_Open, HA_Close)

    This version:
      * Works if a 'timestamp' column exists (sorted chronologically first).
      * Does NOT mutate the original dataframe in-place; returns a copy.
      * Validates required columns.
    """

    def __init__(self, exchange: ExchangeId, candles: list[list]) -> None:
        super().__init__(exchange, candles)

    def get_heikin_ashi(self, df: DataFrame) -> TypedDataFrame[KlineSchema]:
        if df.empty:
            return cast(TypedDataFrame[KlineSchema], df)

        df = self.ensure_ohlc(df)
        work = df.reset_index(drop=True).copy()

        for c in self.ohlc_cols:
            if not is_numeric_dtype(work[c]):
                work.loc[:, c] = to_numeric(work[c], errors="coerce")

        if work[self.ohlc_cols].isna().any().any():
            work = work.dropna(subset=self.ohlc_cols).reset_index(drop=True)
            if work.empty:
                raise ValueError("All OHLC rows became NaN after numeric coercion.")

        ha_close = (work["open"] + work["high"] + work["low"] + work["close"]) / 4.0

        ha_open = ha_close.copy()
        ha_open.iloc[0] = (work["open"].iloc[0] + work["close"].iloc[0]) / 2.0
        for i in range(1, len(work)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2.0

        ha_high = concat([work["high"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = concat([work["low"], ha_open, ha_close], axis=1).min(axis=1)

        work.loc[:, "open"] = ha_open
        work.loc[:, "high"] = ha_high
        work.loc[:, "low"] = ha_low
        work.loc[:, "close"] = ha_close

        return cast(TypedDataFrame[KlineSchema], work)

    def pre_process(
        self,
    ) -> TypedDataFrame[KlineSchema]:
        """Build and return a Heikin Ashi frame at the input interval.

        Higher-timeframe bars can be obtained by calling
        ``resample(df, interval)`` on the raw indexed frame and then passing
        the result through ``get_heikin_ashi``.  Bollinger-band columns can be
        added by passing the result to ``Indicators.bollinguer_spreads(df)``.

        Returns:
            df: Time-indexed HA DataFrame at the interval of the input candles.
        """
        raw_df = self._build_df_from_raw_candles(self.exchange, self.candles)
        raw_df = self._prepare_numeric_ohlcv(raw_df)

        df = self.get_heikin_ashi(raw_df)
        df = cast(TypedDataFrame[KlineSchema], self._set_time_index(df))

        return df

