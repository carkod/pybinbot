class BinanceErrors(Exception):
    def __init__(self, msg, code):
        self.code = code
        self.message = msg
        super().__init__(self.code, self.message)
        return None

    def __str__(self) -> str:
        return f"{self.code} {self.message}"


class InvalidSymbol(BinanceErrors):
    pass


class NotEnoughFunds(BinanceErrors):
    pass
