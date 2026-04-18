from typing import cast

from pandas import DataFrame, to_numeric
from pandas.tseries.frequencies import to_offset
from pandas.api.types import is_numeric_dtype
from pandas import to_datetime
from pandera.typing import DataFrame as TypedDataFrame
from pybinbot.models.signals import KlineSchema
from pybinbot.shared.enums import ExchangeId
from pybinbot.shared.indicators import Indicators


class Candles:
    """
    Base class for candle data processing.

    Provides utilities for building DataFrames from raw exchange candles,
    normalising timestamps, coercing numeric columns, setting time indices,
    and resampling to higher timeframes.

    The ``pre_process`` method returns the raw OHLC candles together with
    a 1-hour resampled frame.  Subclasses (e.g. ``HeikinAshi``) override
    ``pre_process`` to apply additional transformations.
    """

    binance_cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
    ]
    kucoin_cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
    ]

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "open_time",
        "close_time",
        "volume",
        "quote_asset_volume",
    ]

    ohlc_cols = ["open", "high", "low", "close"]

    REQUIRED_COLUMNS = kucoin_cols

    def __init__(self, exchange: ExchangeId, candles: list[list]) -> None:
        self.exchange = exchange
        self.candles = candles

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_timestamps(df: DataFrame, time_cols: list[str]) -> DataFrame:
        """
        Normalize timestamp columns to milliseconds.
        Detects if timestamps are in microseconds (16 digits) and converts to ms (13 digits).
        """
        for col in time_cols:
            if col in df.columns:
                df[col] = to_numeric(df[col], errors="coerce")

                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else 0

                if sample >= 1e15:
                    df[col] = df[col] / 1000

        return df

    # ------------------------------------------------------------------
    # Private DataFrame-building helpers
    # ------------------------------------------------------------------

    def _build_df_from_raw_candles(
        self, exchange: ExchangeId, candles: list[list]
    ) -> DataFrame:
        if exchange == ExchangeId.BINANCE:
            df_raw = DataFrame(candles)
            df = df_raw.iloc[:, : len(self.binance_cols)]
            df.columns = self.binance_cols
            return df

        # KUCOIN (Spot OR Futures)
        df_raw = DataFrame(candles)

        if df_raw.shape[1] == 7:
            sample = df_raw.iloc[0]
            col2 = float(sample[2])
            col3 = float(sample[3])
            is_futures = col2 >= col3

            if is_futures:
                df_raw.columns = [
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "quote_asset_volume",
                ]
            else:
                df_raw.columns = [
                    "open_time",
                    "open",
                    "close",
                    "high",
                    "low",
                    "volume",
                    "quote_asset_volume",
                ]
                df_raw = df_raw[
                    [
                        "open_time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "quote_asset_volume",
                    ]
                ]

            df_raw["close_time"] = df_raw["open_time"]
            return df_raw

        raise ValueError(f"Unexpected KuCoin kline column count: {df_raw.shape[1]}")

    def _prepare_numeric_ohlcv(self, df: DataFrame) -> DataFrame:
        df = self.normalize_timestamps(df, ["open_time", "close_time"])

        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = to_numeric(df[col], errors="coerce")

        return df

    def _set_time_index(self, df: DataFrame) -> DataFrame:
        df = df.copy()
        df["timestamp"] = to_datetime(df["close_time"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        return df

    def _set_open_time_index(self, df: DataFrame) -> DataFrame:
        df = df.copy()
        df["timestamp"] = to_datetime(df["open_time"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        return df

    def resample(self, df_indexed: DataFrame, interval: str) -> DataFrame:
        """Resample *df_indexed* to *interval*.

        Args:
            df_indexed: Time-indexed OHLCV DataFrame.
            interval:   Pandas offset alias (e.g. ``"1h"``, ``"30min"``).
                        Must be **≥ 15 minutes** because the base candles are
                        always fetched at the 15-minute timeframe.

        Raises:
            ValueError: If *interval* resolves to less than 15 minutes.
        """
        offset = to_offset(interval)
        min_offset = to_offset("15min")
        if offset < min_offset:
            raise ValueError(
                f"Resample interval '{interval}' is less than the minimum "
                "allowed interval of 15 minutes."
            )

        resample_aggregation = {
            "open": "first",
            "close": "last",
            "high": "max",
            "low": "min",
            "volume": "sum",
            "quote_asset_volume": "sum",
            "close_time": "first",
            "open_time": "first",
        }
        df_resampled = (
            cast(DataFrame, df_indexed)
            .resample(interval)
            .agg(cast(dict, resample_aggregation))
        )
        df_resampled = df_resampled.dropna(subset=["open", "high", "low", "close"])
        return df_resampled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def pre_process(
        self,
    ) -> tuple[TypedDataFrame[KlineSchema], TypedDataFrame[KlineSchema]]:
        """Build and return raw OHLC frames at the input interval and 1-hour.

        Returns:
            df:     Time-indexed DataFrame at the interval of the input candles.
            df_1h:  Time-indexed DataFrame resampled to 1-hour bars.
        """
        raw_df = self._build_df_from_raw_candles(self.exchange, self.candles)
        raw_df = self._prepare_numeric_ohlcv(raw_df)

        raw_indexed = self._set_time_index(raw_df)
        df_1h = self.resample(raw_indexed, "1h")

        df = Indicators.bollinguer_spreads(cast(TypedDataFrame[KlineSchema], raw_indexed))

        return df, cast(TypedDataFrame[KlineSchema], df_1h)

    @staticmethod
    def post_process(df: TypedDataFrame[KlineSchema]) -> TypedDataFrame[KlineSchema]:
        """
        Post-process the DataFrame by filling missing values and
        converting data types as needed.
        """
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def ensure_ohlc(self, df: DataFrame) -> DataFrame:
        """Validate & coerce a DataFrame into a typed OHLC DataFrame.

        Steps:
        - Verify all REQUIRED_COLUMNS are present (raises ValueError if missing).
        - Coerce numeric columns (including *_time which are expected as ms epoch).
        - Perform early failure if quote_asset_volume becomes entirely NaN.
        - Return the same underlying object cast to DataFrame (no deep copy).
        """
        missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required OHLC columns: {missing}")

        for col in self.numeric_cols:
            if col in df.columns and not is_numeric_dtype(df[col]):
                df[col] = to_numeric(df[col], errors="coerce")

        if (
            "quote_asset_volume" in df.columns
            and df["quote_asset_volume"].notna().sum() == 0
        ):
            raise ValueError(
                "quote_asset_volume column is entirely non-numeric after coercion; cannot compute quote_volume_ratio"
            )

        return df
