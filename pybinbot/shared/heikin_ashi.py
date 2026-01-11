from typing import cast

from pandas import DataFrame, to_numeric, concat
from pandas.api.types import is_numeric_dtype
from pandas import to_datetime
from pybinbot.shared.enums import ExchangeId


class HeikinAshi:
    """
    Dataframe operations shared across projects and Heikin Ashi candle transformation.
    This avoids circular imports and groups related functionality.

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

    def pre_process(self, exchange: ExchangeId, candles: list):
        df_1h = DataFrame()
        df_4h = DataFrame()
        if exchange == ExchangeId.BINANCE:
            df = DataFrame(candles, columns=self.binance_cols)
            columns = self.binance_cols
        else:
            df = DataFrame(candles, columns=self.kucoin_cols)
            columns = self.kucoin_cols

        # Ensure the dataframe has exactly these columns
        if len(df.columns) != len(columns):
            raise ValueError(
                f"Column mismatch: {len(df.columns)} vs expected {len(columns)}"
            )

        # Convert only numeric columns safely
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = to_numeric(df[col], errors="coerce")

        df = self.get_heikin_ashi(df)

        # Ensure close_time is datetime and set as index for proper resampling
        df["timestamp"] = to_datetime(df["close_time"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        # Create aggregation dictionary without close_time and open_time since they're now index-based
        resample_aggregation = {
            "open": "first",
            "close": "last",
            "high": "max",
            "low": "min",
            "volume": "sum",  # Add volume if it exists in your data
            "close_time": "first",
            "open_time": "first",
        }

        # Resample to 4 hour candles for TWAP (align to calendar hours like MongoDB)
        df_4h = df.resample("4h").agg(cast(dict, resample_aggregation))
        # Add open_time and close_time back as columns for 4h data
        df_4h["open_time"] = df_4h.index
        df_4h["close_time"] = df_4h.index

        # Resample to 1 hour candles for Supertrend (align to calendar hours like MongoDB)
        df_1h = df.resample("1h").agg(cast(dict, resample_aggregation))
        # Add open_time and close_time back as columns for 1h data
        df_1h["open_time"] = df_1h.index
        df_1h["close_time"] = df_1h.index

        return df, df_1h, df_4h

    @staticmethod
    def post_process(df: DataFrame) -> DataFrame:
        """
        Post-process the DataFrame by filling missing values and
        converting data types as needed.
        """
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def ensure_ohlc(self, df: DataFrame) -> DataFrame:
        """Validate & coerce a DataFrame into an DataFrame.

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

    def get_heikin_ashi(self, df: DataFrame) -> DataFrame:
        if df.empty:
            return df

        # Validate & coerce using the new type guard helper.
        df = self.ensure_ohlc(df)
        work = df.reset_index(drop=True).copy()

        # Compute HA_Close from ORIGINAL OHLC (still intact in 'work').
        # Ensure numeric dtypes (API feeds sometimes deliver strings)
        for c in self.ohlc_cols:
            # Only attempt conversion if dtype is not already numeric
            if not is_numeric_dtype(work[c]):
                work.loc[:, c] = to_numeric(work[c], errors="coerce")

        if work[self.ohlc_cols].isna().any().any():
            # Drop rows that became NaN after coercion (invalid numeric data)
            work = work.dropna(subset=self.ohlc_cols).reset_index(drop=True)
            if work.empty:
                raise ValueError("All OHLC rows became NaN after numeric coercion.")

        ha_close = (work["open"] + work["high"] + work["low"] + work["close"]) / 4.0

        # Seed HA_Open with original O & C (not HA close).
        ha_open = ha_close.copy()
        ha_open.iloc[0] = (work["open"].iloc[0] + work["close"].iloc[0]) / 2.0
        for i in range(1, len(work)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2.0

        # High / Low derived from max/min of (raw high/low, ha_open, ha_close)
        ha_high = concat([work["high"], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = concat([work["low"], ha_open, ha_close], axis=1).min(axis=1)

        # Assign transformed values.
        work.loc[:, "open"] = ha_open
        work.loc[:, "high"] = ha_high
        work.loc[:, "low"] = ha_low
        work.loc[:, "close"] = ha_close

        return work
