import pytest
from pandas import DataFrame
import pandas as pd
import numpy as np

from pybinbot.shared.heikin_ashi import HeikinAshi
from pybinbot.shared.enums import ExchangeId


class TestHeikinAshi:
    """Test suite for HeikinAshi class and its methods."""

    @pytest.fixture
    def heikin_ashi(self) -> HeikinAshi:
        """Create a HeikinAshi instance for testing."""
        return HeikinAshi()

    @pytest.fixture
    def sample_kucoin_candles(self):
        """Create sample KuCoin format candles for testing."""
        base_time = 1609459200000  # 2021-01-01 00:00:00 UTC in milliseconds
        candles = [
            [
                base_time,
                "100.0",
                "105.0",
                "99.0",
                "102.0",
                "1000.0",
                "102000.0",
            ],
            [
                base_time + 3600000,
                "102.0",
                "110.0",
                "101.0",
                "108.0",
                "1500.0",
                "162000.0",
            ],
            [
                base_time + 7200000,
                "108.0",
                "115.0",
                "107.0",
                "112.0",
                "2000.0",
                "224000.0",
            ],
        ]
        return candles

    @pytest.fixture
    def sample_binance_candles(self):
        """Create sample Binance format candles for testing."""
        base_time = 1609459200000
        candles = [
            [
                base_time,
                "100.0",
                "105.0",
                "99.0",
                "102.0",
                "1000.0",
                base_time + 3599000,
                "102000.0",
                10,
                "500.0",
                "51000.0",
            ],
            [
                base_time + 3600000,
                "102.0",
                "110.0",
                "101.0",
                "108.0",
                "1500.0",
                base_time + 7199000,
                "162000.0",
                15,
                "750.0",
                "81000.0",
            ],
        ]
        return candles

    @pytest.fixture
    def sample_ohlc_dataframe(self):
        """Create a sample OHLC DataFrame for testing."""
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
        """Test that HeikinAshi class can be instantiated."""
        assert heikin_ashi is not None
        assert isinstance(heikin_ashi, HeikinAshi)

    def test_class_attributes(self, heikin_ashi: HeikinAshi):
        """Test that class attributes are properly defined."""
        assert len(heikin_ashi.binance_cols) == 11
        assert len(heikin_ashi.kucoin_cols) == 8
        assert heikin_ashi.ohlc_cols == ["open", "high", "low", "close"]
        assert "open" in heikin_ashi.numeric_cols
        assert "close" in heikin_ashi.numeric_cols

    def test_ensure_ohlc_valid_dataframe(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test ensure_ohlc with a valid DataFrame."""
        result = heikin_ashi.ensure_ohlc(sample_ohlc_dataframe)
        assert isinstance(result, DataFrame)
        assert all(col in result.columns for col in heikin_ashi.REQUIRED_COLUMNS)

    def test_ensure_ohlc_missing_columns(self, heikin_ashi: HeikinAshi):
        """Test ensure_ohlc raises ValueError for missing columns."""
        df = DataFrame({"open": [100.0], "close": [102.0]})
        with pytest.raises(ValueError, match="Missing required OHLC columns"):
            heikin_ashi.ensure_ohlc(df)

    def test_ensure_ohlc_coerces_numeric_columns(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test ensure_ohlc coerces string columns to numeric."""
        # Create DataFrame with string values
        df = sample_ohlc_dataframe.copy()
        df["open"] = df["open"].astype(str)
        df["close"] = df["close"].astype(str)

        result = heikin_ashi.ensure_ohlc(df)
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["close"])

    def test_get_heikin_ashi_empty_dataframe(self, heikin_ashi: HeikinAshi):
        """Test get_heikin_ashi with empty DataFrame."""
        df = DataFrame()
        result = heikin_ashi.get_heikin_ashi(df)
        assert result.empty

    def test_get_heikin_ashi_transformation(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test get_heikin_ashi properly transforms OHLC data."""
        result = heikin_ashi.get_heikin_ashi(sample_ohlc_dataframe)

        # Check that result has same shape and columns as input
        assert result.shape[0] == sample_ohlc_dataframe.shape[0]
        assert all(col in result.columns for col in ["open", "high", "low", "close"])

        # Check that all OHLC values are numeric and non-null
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["close"])
        assert result[["open", "high", "low", "close"]].notna().all().all()

    def test_get_heikin_ashi_formulas(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test that Heikin Ashi formulas are correctly applied."""
        original = sample_ohlc_dataframe.copy()
        result = heikin_ashi.get_heikin_ashi(original)

        # HA_Close should be (O + H + L + C) / 4 from original
        expected_ha_close = (
            original["open"] + original["high"] + original["low"] + original["close"]
        ) / 4.0
        assert np.allclose(
            result["close"].iloc[: len(expected_ha_close)], expected_ha_close
        )

        # HA_High should be >= HA_Close
        assert (result["high"] >= result["close"]).all()

        # HA_Low should be <= HA_Close
        assert (result["low"] <= result["close"]).all()

    def test_post_process_removes_nan(self, heikin_ashi: HeikinAshi):
        """Test post_process removes NaN values."""
        df = DataFrame(
            {
                "col1": [1.0, np.nan, 3.0],
                "col2": [4.0, 5.0, 6.0],
            }
        )
        original_len = len(df)
        result = heikin_ashi.post_process(df)

        # post_process mutates in-place, so check result directly
        assert not result.isna().any().any()
        assert len(result) == original_len - 1  # One NaN row removed
        assert result.index.tolist() == [0, 1]

    def test_post_process_resets_index(self, heikin_ashi: HeikinAshi):
        """Test post_process resets DataFrame index."""
        df = DataFrame({"col1": [1.0, 2.0, 3.0]}, index=[10, 20, 30])
        result = heikin_ashi.post_process(df)

        assert result.index.tolist() == [0, 1, 2]

    def test_pre_process_kucoin(self, heikin_ashi: HeikinAshi, sample_kucoin_candles):
        """Test pre_process with KuCoin candles."""
        df, df_1h, df_4h = heikin_ashi.pre_process(
            ExchangeId.KUCOIN, sample_kucoin_candles
        )

        # Check that all DataFrames are returned and not empty
        assert isinstance(df, DataFrame)
        assert isinstance(df_1h, DataFrame)
        assert isinstance(df_4h, DataFrame)
        assert not df.empty

        # Check that required columns are present
        assert "open" in df.columns
        assert "close" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns

    def test_pre_process_binance(self, heikin_ashi: HeikinAshi, sample_binance_candles):
        """Test pre_process with Binance candles."""
        df, df_1h, df_4h = heikin_ashi.pre_process(
            ExchangeId.BINANCE, sample_binance_candles
        )

        # Check that all DataFrames are returned
        assert isinstance(df, DataFrame)
        assert isinstance(df_1h, DataFrame)
        assert isinstance(df_4h, DataFrame)

    def test_pre_process_resampling(
        self, heikin_ashi: HeikinAshi, sample_kucoin_candles
    ):
        """Test that pre_process correctly resamples to 1h and 4h."""
        df, df_1h, df_4h = heikin_ashi.pre_process(
            ExchangeId.KUCOIN, sample_kucoin_candles
        )

        # 1h candles should have aggregated data
        assert "open" in df_1h.columns
        assert "close" in df_1h.columns
        assert "open_time" in df_1h.columns
        assert "close_time" in df_1h.columns

        # 4h candles should have aggregated data
        assert "open" in df_4h.columns
        assert "close" in df_4h.columns

    def test_pre_process_column_mismatch(self, heikin_ashi: HeikinAshi):
        """Test pre_process raises error on column mismatch."""
        # Create candles with wrong number of columns
        malformed_candles = [
            [1609459200000, "100.0", "105.0"]
        ]  # Only 3 columns instead of 8

        # pandas DataFrame creation will raise ValueError for column mismatch
        with pytest.raises(ValueError):
            heikin_ashi.pre_process(ExchangeId.KUCOIN, malformed_candles)

    def test_get_heikin_ashi_with_string_values(self, heikin_ashi: HeikinAshi):
        """Test get_heikin_ashi handles string OHLC values."""
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
        df = DataFrame(data)

        result = heikin_ashi.get_heikin_ashi(df)
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert result["close"].notna().all()

    def test_get_heikin_ashi_all_nans_raises_error(self, heikin_ashi: HeikinAshi):
        """Test get_heikin_ashi raises error when OHLC becomes all NaN."""
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
        df = DataFrame(data)

        with pytest.raises(ValueError, match="All OHLC rows became NaN"):
            heikin_ashi.get_heikin_ashi(df)

    def test_ensure_ohlc_all_nan_quote_asset_volume(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test ensure_ohlc raises error when quote_asset_volume is all NaN."""
        df = sample_ohlc_dataframe.copy()
        df["quote_asset_volume"] = ["invalid"] * len(df)

        with pytest.raises(
            ValueError, match="quote_asset_volume column is entirely non-numeric"
        ):
            heikin_ashi.ensure_ohlc(df)

    def test_heikin_ashi_does_not_mutate_original(
        self, heikin_ashi: HeikinAshi, sample_ohlc_dataframe: DataFrame
    ):
        """Test that get_heikin_ashi does not mutate the original DataFrame."""
        original = sample_ohlc_dataframe.copy()
        original_copy = original.copy()

        _ = heikin_ashi.get_heikin_ashi(original)

        # Original should remain unchanged
        pd.testing.assert_frame_equal(original, original_copy)

    def test_post_process_mutates_inplace(self, heikin_ashi: HeikinAshi):
        """Test that post_process mutates the original DataFrame in-place."""
        df = DataFrame(
            {
                "col1": [1.0, 2.0, 3.0],
                "col2": [4.0, 5.0, 6.0],
            },
            index=[10, 20, 30],
        )
        original_id = id(df)

        # post_process uses inplace operations
        result = heikin_ashi.post_process(df)

        # Result should be the same object (mutated in-place)
        assert id(result) == original_id
        # Result should have reset index
        assert result.index.tolist() == [0, 1, 2]
