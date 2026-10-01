import pandas as pd
import pytest

from pybinbot.shared import beta

# From the illustrative example: the token consistently moves 1.5x BTC.
BTC_RETURNS = [0.01, -0.02, 0.02, -0.01]
TOKEN_RETURNS = [0.015, -0.03, 0.03, -0.015]


def prices_from_returns(start: float, returns: list[float]) -> pd.Series:
    prices = [start]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return pd.Series(prices)


def test_rolling_beta_matches_known_ratio():
    btc_close = prices_from_returns(100.0, BTC_RETURNS)
    token_close = prices_from_returns(50.0, TOKEN_RETURNS)

    beta_series = beta.rolling_beta(token_close, btc_close, window=4)

    assert beta_series.iloc[-1] == pytest.approx(1.5, rel=1e-6)


def test_latest_beta_none_when_history_too_short():
    btc_close = prices_from_returns(100.0, BTC_RETURNS)
    token_close = prices_from_returns(50.0, TOKEN_RETURNS)

    result = beta.latest_beta(
        token_close, btc_close, window=4, min_periods=beta.DEFAULT_MIN_BETA_PERIODS
    )

    assert result is None


def test_latest_beta_matches_known_ratio_with_enough_history():
    # Repeat the known 1.5x relationship enough times to clear min_periods.
    repeats = beta.DEFAULT_MIN_BETA_PERIODS // len(BTC_RETURNS) + 2
    btc_close = prices_from_returns(100.0, BTC_RETURNS * repeats)
    token_close = prices_from_returns(50.0, TOKEN_RETURNS * repeats)

    result = beta.latest_beta(token_close, btc_close, window=20)

    assert result == pytest.approx(1.5, rel=1e-6)


def test_latest_beta_handles_zero_btc_variance():
    # A perfectly flat BTC series has zero return variance; beta must come
    # back as "unavailable" (None), not raise or divide by zero.
    btc_close = pd.Series([100.0] * 40)
    token_close = prices_from_returns(50.0, TOKEN_RETURNS * 10)

    result = beta.latest_beta(token_close, btc_close, window=4, min_periods=10)

    assert result is None


def test_rolling_beta_aligns_prices_before_taking_returns():
    """A timestamp missing from only one series must drop that row from
    both series before returns are computed, so every return spans the
    same horizon for token and BTC alike. Computing pct_change on each
    series independently first - on its own raw row sequence, ignoring the
    other series' gaps - silently pairs a multi-period return against a
    single-period one under the same label."""
    index = list(range(10))
    btc_close = pd.Series(
        [100.0, 101.0, 99.0, 103.0, 104.0, 108.0, 107.0, 111.0, 110.0, 113.0],
        index=index,
    )
    token_close = pd.Series(
        [50.0, 51.0, 49.0, 53.0, 54.0, 58.0, 57.0, 61.0, 60.0, 63.0],
        index=index,
    )
    # Drop one interior BTC observation only; token keeps every row.
    btc_close_gapped = btc_close.drop(index=5)

    result = beta.rolling_beta(token_close, btc_close_gapped, window=3)

    # The row immediately after the gap is the decisive check: token's own
    # return there (label 5->6, no gap on its side) is negative, but the
    # correct token return spanning the same label-4->6 window BTC actually
    # has is positive. A pre-fix implementation reports the former.
    correct_token_return_across_gap = 57.0 / 54.0 - 1
    prices = pd.DataFrame({"token": token_close, "btc": btc_close_gapped}).dropna()
    expected = prices.pct_change(fill_method=None).dropna()
    assert expected["token"].loc[6] == pytest.approx(correct_token_return_across_gap)
    pd.testing.assert_series_equal(
        result,
        expected["token"].rolling(3).cov(expected["btc"])
        / expected["btc"].rolling(3).var(),
        check_names=False,
    )
