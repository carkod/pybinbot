from numpy import isnan, nan
from pandas import DataFrame, Series

# ~7 days of hourly bars: the minimum aligned-return history before a beta
# estimate is considered stable rather than noise. Scale this (or the
# `window`/`min_periods` arguments) to match the candle interval actually in
# use - this default assumes 1h bars, not whatever interval a caller passes.
DEFAULT_MIN_BETA_PERIODS = 24 * 7


def rolling_beta(token_close: Series, btc_close: Series, *, window: int) -> Series:
    """
    Rolling OLS beta of the token's returns against BTC's returns:

        beta = Cov(r_token, r_btc) / Var(r_btc)

    using percentage returns (``pct_change``), the standard definition, over
    a trailing `window` of aligned observations. The horizon should match
    the strategy this feeds: e.g. ~7-30 days of hourly bars for a next-hour
    signal. A window this short is a deliberate per-caller choice, not a
    default here - shorter windows (a day of hourly bars, for instance)
    produce an unstable estimate.

    Returns a Series aligned to the token/BTC's shared index (inner-joined
    on the two return series, NaN rows dropped first). Values before
    `window` aligned observations have accumulated are NaN - callers must
    not treat a NaN beta as a beta of 0, which would misread as "no BTC
    sensitivity" instead of "not enough history yet".
    """
    returns = DataFrame(
        {"token": token_close.pct_change(), "btc": btc_close.pct_change()}
    ).dropna()
    if returns.empty:
        return Series(dtype=float)

    covariance = returns["token"].rolling(window).cov(returns["btc"])
    variance = returns["btc"].rolling(window).var()
    return covariance / variance.replace(0, nan)


def latest_beta(
    token_close: Series,
    btc_close: Series,
    *,
    window: int,
    min_periods: int = DEFAULT_MIN_BETA_PERIODS,
) -> float | None:
    """
    Current point-in-time beta (the last value of `rolling_beta`), or None
    if fewer than `min_periods` aligned return observations exist yet.
    """
    beta_series = rolling_beta(token_close, btc_close, window=window)
    if len(beta_series) < min_periods:
        return None

    latest = beta_series.iloc[-1]
    return None if isnan(latest) else float(latest)
