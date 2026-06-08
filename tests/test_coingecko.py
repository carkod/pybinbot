from unittest.mock import Mock, call

from pybinbot.apis.coingecko import CoinGecko


def test_get_btc_ohlc_fetches_each_history_range_without_caching(monkeypatch):
    responses = []
    for close in (2.0, 30.0, 3.0):
        response = Mock()
        response.json.return_value = [[1_700_000_000_000, 1.0, 2.0, 0.5, close]]
        responses.append(response)

    get = Mock(side_effect=responses)
    monkeypatch.setattr("pybinbot.apis.coingecko.requests.get", get)

    client = CoinGecko()
    two_days = client.get_btc_ohlc(2)
    thirty_days = client.get_btc_ohlc(30)
    refreshed_two_days = client.get_btc_ohlc(2)

    assert two_days.iloc[0]["close"] == 2.0
    assert thirty_days.iloc[0]["close"] == 30.0
    assert refreshed_two_days.iloc[0]["close"] == 3.0
    assert get.call_args_list == [
        call(
            "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
            params={"vs_currency": "usd", "days": "2"},
        ),
        call(
            "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
            params={"vs_currency": "usd", "days": "30"},
        ),
        call(
            "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc",
            params={"vs_currency": "usd", "days": "2"},
        ),
    ]
