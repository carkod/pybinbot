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

    @staticmethod
    def normalize_timestamps(df: DataFrame, time_cols: list[str]) -> DataFrame:
        """
        Normalize timestamp columns to milliseconds.
        Detects if timestamps are in microseconds (16 digits) and converts to ms (13 digits).
        """
        for col in time_cols:
            if col in df.columns:
                # Convert to numeric first
                df[col] = to_numeric(df[col], errors="coerce")

                # Check if any timestamp is > 13 digits (likely microseconds)
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else 0

                # If timestamp is >= 10^15 (16+ digits), it's likely in microseconds
                if sample >= 1e15:
                    df[col] = df[col] / 1000  # Convert microseconds to milliseconds

        return df

    def pre_process(self, exchange: ExchangeId, candles: list):
        df_1h = DataFrame()
        df_4h = DataFrame()

        if exchange == ExchangeId.BINANCE:
            df_raw = DataFrame(candles)
            df = df_raw.iloc[:, : len(self.binance_cols)]
            df.columns = self.binance_cols

        else:
            # KUCOIN (Spot OR Futures)
            df_raw = DataFrame(candles)

            if df_raw.shape[1] == 7:
                # Could be Spot or Futures → need to normalize order

                # Detect Futures vs Spot by OHLC ordering
                # Futures: open, high, low, close
                # Spot:    open, close, high, low

                # We detect by checking column 2 vs column 3 relationships
                # If col2 >= col3 consistently → likely high/low → Futures

                sample = df_raw.iloc[0]

                col2 = float(sample[2])
                col3 = float(sample[3])

                # Futures pattern: open, high, low, close
                is_futures = col2 >= col3  # high >= low always true in futures format

                if is_futures:
                    # Futures format
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
                    # Spot format
                    df_raw.columns = [
                        "open_time",
                        "open",
                        "close",
                        "high",
                        "low",
                        "volume",
                        "quote_asset_volume",
                    ]

                    # Reorder to canonical OHLC
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

                # KuCoin does not provide close_time → derive it
                df_raw["close_time"] = df_raw["open_time"]

            else:
                raise ValueError(
                    f"Unexpected KuCoin kline column count: {df_raw.shape[1]}"
                )

            df = df_raw

        # Normalize timestamps to milliseconds (detect and convert microseconds)
        df = self.normalize_timestamps(df, ["open_time", "close_time"])

        # Convert numeric safely
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = to_numeric(df[col], errors="coerce")

        df = self.get_heikin_ashi(df)

        df["timestamp"] = to_datetime(df["close_time"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        resample_aggregation = {
            "open": "first",
            "close": "last",
            "high": "max",
            "low": "min",
            "volume": "sum",
            "close_time": "first",
            "open_time": "first",
        }

        df_4h = df.resample("4h").agg(cast(dict, resample_aggregation))
        df_4h["open_time"] = df_4h.index
        df_4h["close_time"] = df_4h.index

        df_1h = df.resample("1h").agg(cast(dict, resample_aggregation))
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
