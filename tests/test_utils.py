
from pybinbot.models.bot_base import BotBase
from pybinbot.shared.utils import convert_to_kucoin_symbol, convert_from_kucoin_symbol
from pybinbot.shared.enums import QuoteAssets


class TestConvertToKucoinSymbol:
    def test_converts_usdc_pair_with_quote_asset_enum(self) -> None:
        bot = BotBase(pair="BTCUSDC", quote_asset=QuoteAssets.USDC, fiat="USDC")

        symbol = convert_to_kucoin_symbol(bot)

        assert symbol == "BTC-USDC"

    def test_converts_usdt_pair_with_quote_asset_enum(self) -> None:
        bot = BotBase(pair="ETHUSDT", quote_asset=QuoteAssets.USDT, fiat="USDT")

        symbol = convert_to_kucoin_symbol(bot)

        assert symbol == "ETH-USDT"

    def test_defaults_to_usdt_when_no_quote_asset(self) -> None:
        # Simulate a bot without a quote_asset attribute
        class MinimalBot:
            def __init__(self, pair: str) -> None:
                self.pair = pair

        bot = MinimalBot(pair="BTCUSDT")

        symbol = convert_to_kucoin_symbol(bot)  # type: ignore[arg-type]

        assert symbol == "BTC-USDT"

    def test_handles_string_quote_asset(self) -> None:
        class BotLike:
            def __init__(self, pair: str, quote_asset: str) -> None:
                self.pair = pair
                self.quote_asset = quote_asset

        bot = BotLike(pair="BTCUSDC", quote_asset="USDC")

        symbol = convert_to_kucoin_symbol(bot)  # type: ignore[arg-type]

        assert symbol == "BTC-USDC"


class TestConvertFromKucoinSymbol:
    def test_converts_standard_symbol(self) -> None:
        assert convert_from_kucoin_symbol("BTC-USDC") == "BTCUSDC"

    def test_converts_multiple_dashes(self) -> None:
        # Defensive: any '-' will be stripped
        assert convert_from_kucoin_symbol("BTC-US-DC") == "BTCUSDC"

    def test_converts_lowercase_symbol(self) -> None:
        assert convert_from_kucoin_symbol("eth-usdt") == "ethusdt"
