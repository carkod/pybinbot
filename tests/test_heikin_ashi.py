from typing import cast

import pytest
from pandas import DataFrame
import pandas as pd
import numpy as np
from pandera.typing import DataFrame as TypedDataFrame

from pybinbot.shared.candles import Candles
from pybinbot.shared.heikin_ashi import HeikinAshi
from pybinbot.shared.enums import ExchangeId
from pybinbot.models.signals import KlineSchema


# ---------------------------------------------------------------------------
# Shared candle factories (reused across test classes via module-level helpers)
# ---------------------------------------------------------------------------

def _make_kucoin_candles(n: int = 48) -> list[list]:
    """Return *n* synthetic KuCoin-style kline rows (futures format, 7 cols)."""
    base_time = 1609459200000  # 2021-01-01 00:00:00 UTC in ms
    candles = []
    for i in range(n):
        open_time = base_time + (i * 300_000)  # 5-minute spacing
        open_price = 100.0 + (i * 0.2)
        close_price = open_price + 0.1
        high_price = close_price + 0.2
        low_price = open_price - 0.2
        volume = 1000.0 + (i * 25.0)
        quote_asset_volume = volume * close_price
        candles.append(
            [
                open_time,
                f"{open_price:.1f}",
                f"{high_price:.1f}",
                f"{low_price:.1f}",
                f"{close_price:.1f}",
                volume,
                quote_asset_volume,
            ]
        )
    return candles


def _make_binance_candles(n: int = 48) -> list[list]:
    """Return *n* synthetic Binance-style kline rows (11 cols)."""
    base_time = 1609459200000
    candles = []
    for i in range(n):
        open_time = base_time + (i * 300_000)
        open_price = 100.0 + (i * 0.2)
        close_price = open_price + 0.1
        high_price = close_price + 0.2
        low_price = open_price - 0.2
        volume = 1000.0 + (i * 25.0)
        quote_asset_volume = volume * close_price
        candles.append(
            [
                open_time,
                f"{open_price:.1f}",
                f"{high_price:.1f}",
                f"{low_price:.1f}",
                f"{close_price:.1f}",
                volume,
                open_time + 299_999,
                quote_asset_volume,
                10 + i,
                volume / 2,
                quote_asset_volume / 2,
            ]
        )
    return candles


# ---------------------------------------------------------------------------
# TestCandles — base-class utilities
# ---------------------------------------------------------------------------


class TestCandles:
    """Test suite for the Candles base class."""

    @pytest.fixture
    def kucoin_candles(self):
        return _make_kucoin_candles()

    @pytest.fixture
    def binance_candles(self):
        return _make_binance_candles()

    @pytest.fixture
    def candles_kucoin(self, kucoin_candles) -> Candles:
        return Candles(ExchangeId.KUCOIN, kucoin_candles)

    @pytest.fixture
    def sample_ohlc_dataframe(self):
        data = {
            "open_time": [1609459200000, 1609462800000, 1609466400000],
            "open": [100.0, 102.0, 108.0],
            "high": [105.0, 110.0, 115.0],
            "low": [99.0, 101.0, 107.0],
            "close": [102.0, 108.0, 112.0],
            "volume": [1000.0, 1500.0, 2000.0],
            "close_time": [1609462799000, 1609466399000, 1609469999000],
            "quote_asset_volume": [102000.0, 162000.0, 224000.0],
        }
        return DataFrame(data)

    def test_instantiation(self, candles_kucoin: Candles):
        assert candles_kucoin is not None
        assert isinstance(candles_kucoin, Candles)

    def test_stores_exchange_and_candles(self, kucoin_candles):
        obj = Candles(ExchangeId.KUCOIN, kucoin_candles)
        assert obj.exchange is ExchangeId.KUCOIN
        assert obj.candles is kucoin_candles

    def test_class_attributes(self, candles_kucoin: Candles):
        assert len(candles_kucoin.binance_cols) == 11
        assert len(candles_kucoin.kucoin_cols) == 8
        assert candles_kucoin.ohlc_cols == ["open", "high", "low", "close"]
        assert "open" in candles_kucoin.numeric_cols
        assert "close" in candles_kucoin.numeric_cols

    def test_pre_process_returns_two_dataframes(self, candles_kucoin: Candles):
        df, df_1h = candles_kucoin.pre_process()
        assert isinstance(df, DataFrame)
        assert isinstance(df_1h, DataFrame)
        assert not df.empty
        assert not df_1h.empty

    def test_pre_process_kucoin_has_ohlc_columns(self, candles_kucoin: Candles):
        df, df_1h = candles_kucoin.pre_process()
        for frame in (df, df_1h):
            for col in ("open", "high", "low", "close"):
                assert col in frame.columns

    def test_pre_process_binance(self, binance_candles):
        obj = Candles(ExchangeId.BINANCE, binance_candles)
        df, df_1h = obj.pre_process()
        assert not df.empty
        assert not df_1h.empty

    def test_pre_process_1h_has_ohlc_columns(self, candles_kucoin: Candles):
        _, df_1h = candles_kucoin.pre_process()
        assert "open" in df_1h.columns
        assert "close" in df_1h.columns
        assert "open_time" in df_1h.columns
        assert "close_time" in df_1h.columns

    def test_ensure_ohlc_valid_dataframe(
        self, candles_kucoin: Candles, sample_ohlc_dataframe: DataFrame
    ):
        result = candles_kucoin.ensure_ohlc(sample_ohlc_dataframe)
        assert isinstance(result, DataFrame)
        assert all(col in result.columns for col in candles_kucoin.REQUIRED_COLUMNS)

    def test_ensure_ohlc_missing_columns(self, candles_kucoin: Candles):
        df = DataFrame({"open": [100.0], "close": [102.0]})
        with pytest.raises(ValueError, match="Missing required OHLC columns"):
            candles_kucoin.ensure_ohlc(df)

    def test_ensure_ohlc_coerces_numeric_columns(
        self, candles_kucoin: Candles, sample_ohlc_dataframe: DataFrame
    ):
        df = sample_ohlc_dataframe.copy()
        df["open"] = df["open"].astype(str)
        df["close"] = df["close"].astype(str)

        result = candles_kucoin.ensure_ohlc(df)
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["close"])

    def test_ensure_ohlc_all_nan_quote_asset_volume(
        self, candles_kucoin: Candles, sample_ohlc_dataframe: DataFrame
    ):
        df = sample_ohlc_dataframe.copy()
        df["quote_asset_volume"] = ["invalid"] * len(df)
        with pytest.raises(
            ValueError, match="quote_asset_volume column is entirely non-numeric"
        ):
            candles_kucoin.ensure_ohlc(df)

    def test_post_process_removes_nan(self, candles_kucoin: Candles):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame({"col1": [1.0, np.nan, 3.0], "col2": [4.0, 5.0, 6.0]}),
        )
        result = candles_kucoin.post_process(df)
        assert not result.isna().any().any()
        assert len(result) == 2
        assert result.index.tolist() == [0, 1]

    def test_post_process_resets_index(self, candles_kucoin: Candles):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame({"col1": [1.0, 2.0, 3.0]}, index=[10, 20, 30]),
        )
        result = candles_kucoin.post_process(df)
        assert result.index.tolist() == [0, 1, 2]

    def test_post_process_mutates_inplace(self, candles_kucoin: Candles):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame(
                {"col1": [1.0, 2.0, 3.0], "col2": [4.0, 5.0, 6.0]},
                index=[10, 20, 30],
            ),
        )
        original_id = id(df)
        result = candles_kucoin.post_process(df)
        assert id(result) == original_id
        assert result.index.tolist() == [0, 1, 2]


# ---------------------------------------------------------------------------
# TestHeikinAshi
# ---------------------------------------------------------------------------


class TestHeikinAshi:
    """Test suite for HeikinAshi class and its methods."""

    @pytest.fixture
    def kucoin_candles(self):
        return _make_kucoin_candles()

    @pytest.fixture
    def binance_candles(self):
        return _make_binance_candles()

    @pytest.fixture
    def heikin_ashi(self, kucoin_candles) -> HeikinAshi:
        return HeikinAshi(ExchangeId.KUCOIN, kucoin_candles)

    @pytest.fixture
    def sample_ohlc_dataframe(self):
        data = {
            "open_time": [1609459200000, 1609462800000, 1609466400000],
            "open": [100.0, 102.0, 108.0],
            "high": [105.0, 110.0, 115.0],
            "low": [99.0, 101.0, 107.0],
            "close": [102.0, 108.0, 112.0],
            "volume": [1000.0, 1500.0, 2000.0],
            "close_time": [1609462799000, 1609466399000, 1609469999000],
            "quote_asset_volume": [102000.0, 162000.0, 224000.0],
        }
        return DataFrame(data)

    def test_heikin_ashi_instantiation(self, heikin_ashi: HeikinAshi):
        assert heikin_ashi is not None
        assert isinstance(heikin_ashi, HeikinAshi)

    def test_is_subclass_of_candles(self, heikin_ashi: HeikinAshi):
        assert isinstance(heikin_ashi, Candles)

    def test_stores_exchange_and_candles(self, kucoin_candles):
        ha = HeikinAshi(ExchangeId.KUCOIN, kucoin_candles)
        assert ha.exchange is ExchangeId.KUCOIN
        assert ha.candles is kucoin_candles

    def test_class_attributes(self, heikin_ashi: HeikinAshi):
        assert len(heikin_ashi.binance_cols) == 11
        assert len(heikin_ashi.kucoin_cols) == 8
        assert heikin_ashi.ohlc_cols == ["open", "high", "low", "close"]
        assert "open" in heikin_ashi.numeric_cols
        assert "close" in heikin_ashi.numeric_cols

    def test_ensure_ohlc_valid_dataframe(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        result = heikin_ashi.ensure_ohlc(sample_ohlc_dataframe)
        assert isinstance(result, DataFrame)
        assert all(col in result.columns for col in heikin_ashi.REQUIRED_COLUMNS)

    def test_ensure_ohlc_missing_columns(self, heikin_ashi: HeikinAshi):
        df = DataFrame({"open": [100.0], "close": [102.0]})
        with pytest.raises(ValueError, match="Missing required OHLC columns"):
            heikin_ashi.ensure_ohlc(df)

    def test_ensure_ohlc_coerces_numeric_columns(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        df = sample_ohlc_dataframe.copy()
        df["open"] = df["open"].astype(str)
        df["close"] = df["close"].astype(str)

        result = heikin_ashi.ensure_ohlc(df)
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["close"])

    def test_get_heikin_ashi_empty_dataframe(self, heikin_ashi: HeikinAshi):
        df = DataFrame()
        result = heikin_ashi.get_heikin_ashi(df)
        assert result.empty

    def test_get_heikin_ashi_transformation(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        result = heikin_ashi.get_heikin_ashi(sample_ohlc_dataframe)

        assert result.shape[0] == sample_ohlc_dataframe.shape[0]
        assert all(col in result.columns for col in ["open", "high", "low", "close"])
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["close"])
        assert result[["open", "high", "low", "close"]].notna().all().all()

    def test_get_heikin_ashi_formulas(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        original = sample_ohlc_dataframe.copy()
        result = heikin_ashi.get_heikin_ashi(original)

        expected_ha_close = (
            original["open"] + original["high"] + original["low"] + original["close"]
        ) / 4.0
        assert np.allclose(result["close"].iloc[: len(expected_ha_close)], expected_ha_close)

        assert (result["high"] >= result["close"]).all()
        assert (result["low"] <= result["close"]).all()

    def test_get_heikin_ashi_with_string_values(self, heikin_ashi: HeikinAshi):
        data = {
            "open_time": [1609459200000],
            "open": ["100.0"],
            "high": ["105.0"],
            "low": ["99.0"],
            "close": ["102.0"],
            "volume": ["1000.0"],
            "close_time": [1609462799000],
            "quote_asset_volume": ["102000.0"],
        }
        result = heikin_ashi.get_heikin_ashi(DataFrame(data))
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert result["close"].notna().all()

    def test_get_heikin_ashi_all_nans_raises_error(self, heikin_ashi: HeikinAshi):
        data = {
            "open_time": [1609459200000],
            "open": ["invalid"],
            "high": ["invalid"],
            "low": ["invalid"],
            "close": ["invalid"],
            "volume": [1000.0],
            "close_time": [1609462799000],
            "quote_asset_volume": [102000.0],
        }
        with pytest.raises(ValueError, match="All OHLC rows became NaN"):
            heikin_ashi.get_heikin_ashi(DataFrame(data))

    def test_heikin_ashi_does_not_mutate_original(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        original = sample_ohlc_dataframe.copy()
        original_copy = original.copy()
        _ = heikin_ashi.get_heikin_ashi(original)
        pd.testing.assert_frame_equal(original, original_copy)

    def test_ensure_ohlc_all_nan_quote_asset_volume(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        df = sample_ohlc_dataframe.copy()
        df["quote_asset_volume"] = ["invalid"] * len(df)
        with pytest.raises(
            ValueError, match="quote_asset_volume column is entirely non-numeric"
        ):
            heikin_ashi.ensure_ohlc(df)

    def test_post_process_removes_nan(self, heikin_ashi: HeikinAshi):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame({"col1": [1.0, np.nan, 3.0], "col2": [4.0, 5.0, 6.0]}),
        )
        result = heikin_ashi.post_process(df)
        assert not result.isna().any().any()
        assert len(result) == 2
        assert result.index.tolist() == [0, 1]

    def test_post_process_resets_index(self, heikin_ashi: HeikinAshi):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame({"col1": [1.0, 2.0, 3.0]}, index=[10, 20, 30]),
        )
        result = heikin_ashi.post_process(df)
        assert result.index.tolist() == [0, 1, 2]

    def test_post_process_mutates_inplace(self, heikin_ashi: HeikinAshi):
        df = cast(
            TypedDataFrame[KlineSchema],
            DataFrame(
                {"col1": [1.0, 2.0, 3.0], "col2": [4.0, 5.0, 6.0]},
                index=[10, 20, 30],
            ),
        )
        original_id = id(df)
        result = heikin_ashi.post_process(df)
        assert id(result) == original_id
        assert result.index.tolist() == [0, 1, 2]

    def test_pre_process_returns_two_dataframes(self, heikin_ashi: HeikinAshi):
        result = heikin_ashi.pre_process()
        assert len(result) == 2
        df, df_1h = result
        assert isinstance(df, DataFrame)
        assert isinstance(df_1h, DataFrame)
        assert not df.empty
        assert not df_1h.empty

    def test_pre_process_kucoin_has_ohlc_columns(self, heikin_ashi: HeikinAshi):
        df, df_1h = heikin_ashi.pre_process()
        for frame in (df, df_1h):
            for col in ("open", "high", "low", "close"):
                assert col in frame.columns

    def test_pre_process_binance(self, binance_candles):
        ha = HeikinAshi(ExchangeId.BINANCE, binance_candles)
        df, df_1h = ha.pre_process()
        assert not df.empty
        assert not df_1h.empty

    def test_pre_process_1h_has_ohlc_columns(self, heikin_ashi: HeikinAshi):
        _, df_1h = heikin_ashi.pre_process()
        assert "open" in df_1h.columns
        assert "close" in df_1h.columns
        assert "open_time" in df_1h.columns
        assert "close_time" in df_1h.columns

    def test_pre_process_applies_bollinguer_spreads(self, heikin_ashi: HeikinAshi):
        """df returned by pre_process must carry bb_upper, bb_lower, bb_mid columns."""
        df, _ = heikin_ashi.pre_process()
        assert "bb_upper" in df.columns
        assert "bb_lower" in df.columns
        assert "bb_mid" in df.columns

    def test_pre_process_bb_columns_are_numeric(self, heikin_ashi: HeikinAshi):
        df, _ = heikin_ashi.pre_process()
        assert pd.api.types.is_numeric_dtype(df["bb_upper"])
        assert pd.api.types.is_numeric_dtype(df["bb_lower"])
        assert pd.api.types.is_numeric_dtype(df["bb_mid"])

    def test_pre_process_bb_upper_gte_lower(self, heikin_ashi: HeikinAshi):
        df, _ = heikin_ashi.pre_process()
        valid = df[["bb_upper", "bb_lower"]].dropna()
        assert (valid["bb_upper"] >= valid["bb_lower"]).all()

    def test_pre_process_column_mismatch(self):
        malformed = [[1609459200000, "100.0", "105.0"]]
        ha = HeikinAshi(ExchangeId.KUCOIN, malformed)
        with pytest.raises(ValueError):
            ha.pre_process()

