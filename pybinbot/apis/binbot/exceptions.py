class BinbotErrors(Exception):
    def __init__(self, msg, code=None):
        self.message = msg
        self.code = code
        super().__init__(self.message)
        return None

    def __str__(self) -> str:
        return f"{self.message}"


class IsolateBalanceError(BinbotErrors):
    pass


class QuantityTooLow(BinbotErrors):
    """
    Raised when LOT_SIZE filter error triggers
    This error should happen in the least cases,
    unless purposedly triggered to check quantity
    e.g. BTC = 0.0001 amounts are usually so small that it's hard to see if it's nothing or a considerable amount compared to others
    """

    pass


class MarginShortError(BinbotErrors):
    pass


class MarginLoanNotFound(BinbotErrors):
    pass


class DeleteOrderError(BinbotErrors):
    pass


class LowBalanceCleanupError(BinbotErrors):
    pass


class DealCreationError(BinbotErrors):
    pass


class SaveBotError(BinbotErrors):
    pass


class InsufficientBalance(BinbotErrors):
    """
    Insufficient total_buy_qty to deactivate
    """

    pass
