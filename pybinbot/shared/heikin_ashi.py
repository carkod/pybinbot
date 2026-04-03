import logging
from time import time
from typing import cast

from numpy import isclose
from pandas import DataFrame, to_numeric, concat
from pandas.api.types import is_numeric_dtype
from pandas import to_datetime
from pandera.typing import DataFrame as TypedDataFrame
from pybinbot.models.signals import KlineSchema
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

    PARITY_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000
    _last_parity_check_ms_by_symbol: dict[str, int] = {}

    @classmethod
    def is_15m_parity_check_due(cls, parity_symbol: str | None) -> bool:
        if parity_symbol is None:
            logging.error(
                "Skipping 15m parity check: symbol=%s interval=%s",
                parity_symbol,
                "15m",
            )
            return False

        symbol_key = parity_symbol
        now_ms = int(time() * 1000)
        last_run_ms = cls._last_parity_check_ms_by_symbol.get(symbol_key, 0)
        return now_ms - last_run_ms >= cls.PARITY_CHECK_INTERVAL_MS

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

    def _build_df_from_raw_candles(
        self, exchange: ExchangeId, candles: list
    ) -> DataFrame:
        if exchange == ExchangeId.BINANCE:
            df_raw = DataFrame(candles)
            df = df_raw.iloc[:, : len(self.binance_cols)]
            df.columns = self.binance_cols
            return df

        # KUCOIN (Spot OR Futures)
        df_raw = DataFrame(candles)

        if df_raw.shape[1] == 7:
            # Could be Spot or Futures -> normalize order.
            sample = df_raw.iloc[0]
            col2 = float(sample[2])
            col3 = float(sample[3])
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

            # KuCoin does not provide close_time -> derive it
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

    def _build_15m_from_5m(self, df_indexed: DataFrame) -> DataFrame:
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
        df_15m = (
            cast(DataFrame, df_indexed)
            .resample("15min")
            .agg(cast(dict, resample_aggregation))
        )
        df_15m = df_15m.dropna(subset=["open", "high", "low", "close"])
        return df_15m

    def _run_15m_parity_check(
        self,
        exchange: ExchangeId,
        synthetic_15m_df: DataFrame,
        parity_exchange_15m_candles: list | None,
        parity_symbol: str | None,
    ) -> None:
        if not parity_exchange_15m_candles:
            return

        if parity_symbol is None:
            logging.error(
                "Skipping 15m parity check: symbol=%s interval=%s",
                parity_symbol,
                "15m",
            )
            return

        symbol_key = parity_symbol
        if not self.is_15m_parity_check_due(parity_symbol):
            return

        self._last_parity_check_ms_by_symbol[symbol_key] = int(time() * 1000)

        exchange_15m_df = self._build_df_from_raw_candles(
            exchange, parity_exchange_15m_candles
        )
        exchange_15m_df = self._prepare_numeric_ohlcv(exchange_15m_df)
        exchange_15m_df = self._set_time_index(exchange_15m_df)

        cols = ["open", "high", "low", "close", "volume"]
        synthetic = synthetic_15m_df[cols].copy()
        exchange_direct = exchange_15m_df[cols].copy()

        common_idx = synthetic.index.intersection(exchange_direct.index)
        if common_idx.empty:
            logging.warning(
                "15m parity discrepancy detected for symbol=%s: no overlapping candle timestamps",
                symbol_key,
            )
            return

        common_idx = common_idx[-50:]
        synthetic = synthetic.loc[common_idx]
        exchange_direct = exchange_direct.loc[common_idx]

        tolerances = {
            "open": (1e-8, 1e-8),
            "high": (1e-8, 1e-8),
            "low": (1e-8, 1e-8),
            "close": (1e-8, 1e-8),
            "volume": (1e-6, 1e-8),
        }

        for col in cols:
            rtol, atol = tolerances[col]
            matches = isclose(
                synthetic[col].to_numpy(),
                exchange_direct[col].to_numpy(),
                rtol=rtol,
                atol=atol,
            )
            if not matches.all():
                mismatch_pos = int((~matches).argmax())
                mismatch_ts = common_idx[mismatch_pos]
                logging.warning(
                    "15m parity discrepancy detected for symbol=%s: %s mismatch at %s (synthetic=%s exchange=%s)",
                    symbol_key,
                    col,
                    mismatch_ts,
                    synthetic.iloc[mismatch_pos][col],
                    exchange_direct.iloc[mismatch_pos][col],
                )
                return

    def pre_process(
        self,
        exchange: ExchangeId,
        candles: list,
        parity_symbol: str | None = None,
        parity_exchange_15m_candles: list | None = None,
    ):
        df_1h = DataFrame()
        df_4h = DataFrame()

        raw_df = self._build_df_from_raw_candles(exchange, candles)
        raw_df = self._prepare_numeric_ohlcv(raw_df)

        # 15m synthetic candles from 5m input for parity/backtest checks and strategy frame.
        raw_indexed = self._set_time_index(raw_df)
        synthetic_15m_df = self._build_15m_from_5m(raw_indexed)
        self._run_15m_parity_check(
            exchange=exchange,
            synthetic_15m_df=synthetic_15m_df,
            parity_exchange_15m_candles=parity_exchange_15m_candles,
            parity_symbol=parity_symbol,
        )

        # Base 5m Heikin Ashi dataframe.
        df = self.get_heikin_ashi(raw_df)
        df = cast(TypedDataFrame[KlineSchema], self._set_time_index(df))

        # 15m Heikin Ashi dataframe derived from synthetic 15m candles.
        df_15m = self.get_heikin_ashi(synthetic_15m_df.reset_index(drop=True))
        df_15m = cast(TypedDataFrame[KlineSchema], self._set_time_index(df_15m))

        resample_aggregation = {
            "open": "first",
            "close": "last",
            "high": "max",
            "low": "min",
            "volume": "sum",
            "close_time": "first",
            "open_time": "first",
        }

        plain_df = cast(DataFrame, df_15m)
        df_4h = plain_df.resample("4h").agg(cast(dict, resample_aggregation))
        df_4h["open_time"] = df_4h.index
        df_4h["close_time"] = df_4h.index

        df_1h = plain_df.resample("1h").agg(cast(dict, resample_aggregation))
        df_1h["open_time"] = df_1h.index
        df_1h["close_time"] = df_1h.index

        return df, df_15m, df_1h, df_4h

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

    def get_heikin_ashi(self, df: DataFrame) -> TypedDataFrame[KlineSchema]:
        if df.empty:
            return cast(TypedDataFrame[KlineSchema], df)

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

        return cast(TypedDataFrame[KlineSchema], work)
