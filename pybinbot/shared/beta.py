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

    Returns a Series aligned to the token/BTC's shared index. The two close
    price series are inner-joined *before* returns are computed (a missing
    timestamp on either side drops that row from both), so every return in
    the resulting frame spans the same pair of timestamps for token and
    BTC alike - computing each return independently first and joining
    afterwards can silently pair a token return against a BTC return over
    a different horizon whenever one series is missing a timestamp the
    other has. `fill_method=None` disables pandas' pct_change forward-fill
    (deprecated but still the pandas 2.2 default): an internal gap must
    produce a NaN return to be dropped, not a synthetic zero computed
    against a stale, forward-filled price.

    Values before `window` aligned observations have accumulated are NaN -
    callers must not treat a NaN beta as a beta of 0, which would misread
    as "no BTC sensitivity" instead of "not enough history yet".
    """
    prices = DataFrame({"token": token_close, "btc": btc_close}).dropna()
    if prices.empty:
        return Series(dtype=float)

    returns = prices.pct_change(fill_method=None).dropna()
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
