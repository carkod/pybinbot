from pybinbot.models.bot_base import BotBase


def convert_to_kucoin_symbol(bot: BotBase) -> str:
    """
    Convert symbol to KuCoin format if exchange is KuCoin
    e.g. BTCUSDC -> BTC-USDC
    """
    quote = (
        bot.pair.replace(
            bot.pair.replace(
                bot.quote_asset.value
                if hasattr(bot.quote_asset, "value")
                else str(bot.quote_asset),
                "",
            ),
            "",
        )
        if hasattr(bot, "quote_asset") and bot.quote_asset
        else "USDT"
    )
    base = bot.pair.replace(quote, "")
    kucoin_symbol = f"{base}-{quote}"
    return kucoin_symbol


def convert_from_kucoin_symbol(kucoin_symbol: str) -> str:
    """
    Convert symbol from KuCoin format to standard format
    e.g. BTC-USDC -> BTCUSDC
    """
    return kucoin_symbol.replace("-", "")
