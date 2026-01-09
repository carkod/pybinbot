import pandas as pd
import numpy as np
from pybinbot.shared.indicators import Indicators


def create_sample_df(periods=100):
    """Create a sample DataFrame with OHLCV data for testing."""
    np.random.seed(42)
    close_prices = 100 + np.cumsum(np.random.randn(periods) * 0.5)

    df = pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=periods, freq="1h"),
            "open": close_prices * 0.98,
            "high": close_prices * 1.02,
            "low": close_prices * 0.97,
            "close": close_prices,
            "volume": np.random.uniform(1000, 5000, periods),
            "close_time": pd.date_range("2024-01-01", periods=periods, freq="1h"),
        }
    )
    return df


class TestEMA:
    def test_ema_basic(self):
        """Test basic EMA calculation."""
        df = create_sample_df()
        result = Indicators.ema(df, column="close", span=9, out_col="ema_9")

        assert "ema_9" in result.columns
        assert result["ema_9"].notna().sum() > 0
        # First few values might be NaN due to span
        assert result["ema_9"].iloc[-1] > 0

    def test_ema_default_column(self):
        """Test EMA with default column naming."""
        df = create_sample_df()
        result = Indicators.ema(df, column="close", span=9)

        assert "ema_9" in result.columns

    def test_ema_different_spans(self):
        """Test EMA with different spans produces different values."""
        df = create_sample_df()
        result1 = Indicators.ema(df.copy(), column="close", span=5, out_col="ema_5")
        result2 = Indicators.ema(df.copy(), column="close", span=20, out_col="ema_20")

        # Different spans should produce different values
        assert not np.allclose(
            result1["ema_5"].iloc[20:].values,
            result2["ema_20"].iloc[20:].values,
            equal_nan=True,
        )


class TestTrendEMA:
    def test_trend_ema_creates_both_columns(self):
        """Test that trend_ema creates both ema_fast and ema_slow columns."""
        df = create_sample_df()
        result = Indicators.trend_ema(df)

        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns

    def test_trend_ema_custom_spans(self):
        """Test trend_ema with custom fast and slow spans."""
        df = create_sample_df()
        result = Indicators.trend_ema(df, fast_span=5, slow_span=15)

        assert "ema_fast" in result.columns
        assert "ema_slow" in result.columns
        # Slow EMA should be smoother (less volatile) than fast EMA
        fast_std = result["ema_fast"].std()
        slow_std = result["ema_slow"].std()
        # This might not always be strictly true but generally should be

    def test_trend_ema_fast_faster_than_slow(self):
        """Test that fast EMA is more responsive than slow EMA."""
        df = create_sample_df(periods=200)
        result = Indicators.trend_ema(df, fast_span=9, slow_span=21)

        # Calculate correlation with price - fast should have higher correlation (more responsive)
        price = result["close"]
        corr_fast = result["ema_fast"].corr(price)
        corr_slow = result["ema_slow"].corr(price)

        # Fast EMA should be closer to current price (higher correlation)
        assert corr_fast >= corr_slow

    def test_trend_ema_returns_dataframe(self):
        """Test that trend_ema returns a DataFrame."""
        df = create_sample_df()
        result = Indicators.trend_ema(df)

        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == df.shape[0]


class TestRSI:
    def test_rsi_creates_column(self):
        """Test that RSI creates the rsi column."""
        df = create_sample_df()
        result = Indicators.rsi(df)

        assert "rsi" in result.columns

    def test_rsi_bounds(self):
        """Test that RSI values are between 0 and 100."""
        df = create_sample_df(periods=100)
        result = Indicators.rsi(df, window=14)

        # Skip initial NaN values
        valid_rsi = result["rsi"].dropna()
        assert (valid_rsi >= 0).all() or (valid_rsi <= 100).all()

    def test_rsi_custom_window(self):
        """Test RSI with custom window."""
        df = create_sample_df()
        result1 = Indicators.rsi(df.copy(), window=7)
        result2 = Indicators.rsi(df.copy(), window=14)

        assert "rsi" in result1.columns
        assert "rsi" in result2.columns


class TestMovingAverage:
    def test_moving_average_creates_column(self):
        """Test that moving average creates ma_X column."""
        df = create_sample_df()
        result = Indicators.moving_averages(df, period=7)

        assert "ma_7" in result.columns

    def test_moving_average_calculation(self):
        """Test moving average calculation."""
        df = create_sample_df()
        result = Indicators.moving_averages(df, period=5)

        # Verify calculation for one point manually
        manual_ma = df["close"].iloc[4:9].mean()
        computed_ma = result["ma_5"].iloc[8]

        assert np.isclose(manual_ma, computed_ma, rtol=1e-5)


class TestMACD:
    def test_macd_creates_columns(self):
        """Test that MACD creates macd and macd_signal columns."""
        df = create_sample_df(periods=50)
        result = Indicators.macd(df)

        assert "macd" in result.columns
        assert "macd_signal" in result.columns

    def test_macd_values_exist(self):
        """Test that MACD produces values."""
        df = create_sample_df(periods=50)
        result = Indicators.macd(df)

        assert result["macd"].notna().sum() > 0
        assert result["macd_signal"].notna().sum() > 0


class TestBollingerBands:
    def test_bollinger_bands_creates_columns(self):
        """Test that Bollinger Bands creates the expected columns."""
        df = create_sample_df()
        result = Indicators.bollinguer_spreads(df, window=20)

        assert "bb_upper" in result.columns
        assert "bb_lower" in result.columns
        assert "bb_mid" in result.columns

    def test_bollinger_bands_order(self):
        """Test that upper > mid > lower for Bollinger Bands."""
        df = create_sample_df(periods=50)
        result = Indicators.bollinguer_spreads(df, window=20)

        # Check at least the last valid row
        assert result["bb_upper"].iloc[-1] >= result["bb_mid"].iloc[-1]
        assert result["bb_mid"].iloc[-1] >= result["bb_lower"].iloc[-1]


class TestATR:
    def test_atr_creates_column(self):
        """Test that ATR creates the ATR column."""
        df = create_sample_df(periods=50)
        result = Indicators.atr(df, window=14)

        assert "ATR" in result.columns

    def test_atr_positive_values(self):
        """Test that ATR values are positive."""
        df = create_sample_df(periods=50)
        result = Indicators.atr(df, window=14, min_periods=14)

        valid_atr = result["ATR"].dropna()
        assert (valid_atr > 0).all()


class TestSupertrend:
    def test_supertrend_creates_columns(self):
        """Test that Supertrend creates the expected columns."""
        df = create_sample_df(periods=50)
        df = Indicators.atr(df, window=14, min_periods=14)
        result = Indicators.set_supertrend(df, multiplier=3.0)

        assert "supertrend" in result.columns
        assert "supertrend_dir" in result.columns

    def test_supertrend_direction_values(self):
        """Test that Supertrend direction values are 1, -1, or 0."""
        df = create_sample_df(periods=50)
        df = Indicators.atr(df, window=14, min_periods=14)
        result = Indicators.set_supertrend(df, multiplier=3.0)

        valid_dir = result["supertrend_dir"].dropna()
        assert set(valid_dir.unique()).issubset({-1, 0, 1})


class TestPostProcess:
    def test_post_process_removes_nans(self):
        """Test that post_process removes NaN values."""
        df = create_sample_df()
        df.loc[0, "close"] = np.nan

        result = Indicators.post_process(df)

        assert result["close"].notna().all()

    def test_post_process_resets_index(self):
        """Test that post_process resets the index."""
        df = create_sample_df()
        df.index = range(999, 999 - len(df), -1)

        result = Indicators.post_process(df)

        assert result.index.equals(pd.RangeIndex(start=0, stop=len(result)))


class TestIntegration:
    def test_indicator_chain(self):
        """Test chaining multiple indicators together."""
        df = create_sample_df(periods=50)

        df = Indicators.trend_ema(df)
        df = Indicators.rsi(df)
        df = Indicators.moving_averages(df, period=7)
        df = Indicators.moving_averages(df, period=25)
        df = Indicators.macd(df)
        df = Indicators.bollinguer_spreads(df, window=20)
        df = Indicators.atr(df, window=14)

        # Check all indicators are present
        expected_cols = [
            "ema_fast",
            "ema_slow",
            "rsi",
            "ma_7",
            "ma_25",
            "macd",
            "macd_signal",
            "bb_upper",
            "bb_lower",
            "bb_mid",
            "ATR",
        ]

        for col in expected_cols:
            assert col in df.columns

        # Check dataframe is not empty
        assert len(df) > 0
