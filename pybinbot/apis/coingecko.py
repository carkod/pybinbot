import requests
from pandas import DataFrame, to_datetime


class CoinGecko:
    """
    CoinGecko API client for fetching cryptocurrency data.
    """

    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    def get_all_categories(self) -> list[str]:
        url = f"{self.base_url}/coins/categories"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return [cat["id"] for cat in r.json()]

    def get_coins_in_category(self, category_id: str) -> list:
        page = 1
        all_coins: list[dict] = []
        while True:
            params = {
                "vs_currency": "usd",
                "category": category_id,
                "order": "market_cap_desc",
                "per_page": "250",
                "page": str(page),
            }
            r = requests.get(
                f"{self.base_url}/coins/markets", params=params, timeout=15
            )
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            all_coins.extend(data)
            page += 1
        return all_coins

    def get_btc_ohlc(self, days: int = 2) -> DataFrame:
        """Return a time-indexed OHLC DataFrame for Bitcoin via CoinGecko.

        Args:
            days: How many days of history to request. CoinGecko returns
                  different bar granularity depending on this value:
                  1–2 days → 30-min bars, 3–30 days → 4-hour bars,
                  31+ days → 4-day bars. Default 2 gives ~96 30-min
                  candles, enough for a window-20 Bollinger calculation.

        Returns:
            DataFrame with columns [open_time, open, high, low, close],
            indexed by a UTC DatetimeIndex derived from open_time.
        """
        url = f"{self.base_url}/coins/bitcoin/ohlc"
        r = requests.get(
            url, params={"vs_currency": "usd", "days": str(days)}, timeout=15
        )
        r.raise_for_status()
        # Response: [[timestamp_ms, open, high, low, close], ...]
        df = DataFrame(r.json(), columns=["open_time", "open", "high", "low", "close"])
        df["timestamp"] = to_datetime(df["open_time"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df
