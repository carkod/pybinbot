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
