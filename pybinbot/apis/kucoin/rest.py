from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.model import TransportOptionBuilder
from kucoin_universal_sdk.model import ClientOptionBuilder
from kucoin_universal_sdk.model import (
    GLOBAL_API_ENDPOINT,
    GLOBAL_FUTURES_API_ENDPOINT,
)


class KucoinRest:
    def __init__(self, key: str, secret: str, passphrase: str):
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.http_transport_option = (
            TransportOptionBuilder()
            .set_keep_alive(True)
            .set_max_pool_size(10)
            .set_max_connection_per_pool(10)
            .build()
        )

    def setup_client(self) -> DefaultClient:
        client_option = (
            ClientOptionBuilder()
            .set_key(self.key)
            .set_secret(self.secret)
            .set_passphrase(self.passphrase)
            .set_spot_endpoint(GLOBAL_API_ENDPOINT)
            .set_transport_option(self.http_transport_option)
            .build()
        )
        self.client = DefaultClient(client_option)
        return self.client

    def setup_futures_api(self) -> None:
        """
        Separates spot and futures as they have completely different interfaces
        also creates consistency and resusability of variable
        and attribute naming.

        The methods here should be mostly fixated
        not often changed or tweaked.
        
        :param self: Description
        """
        client_option = (
            ClientOptionBuilder()
            .set_key(self.key)
            .set_secret(self.secret)
            .set_passphrase(self.passphrase)
            .set_futures_endpoint(GLOBAL_FUTURES_API_ENDPOINT)
            .set_transport_option(self.http_transport_option)
            .build()
        )
        self.futures_client = DefaultClient(client_option)
        self.transfer_api = self.futures_client.rest_service().get_account_service().get_transfer_api()
        self.futures_service = self.futures_client.rest_service().get_futures_service()
        self.futures_market_api = self.futures_service.get_market_api()
        self.futures_order_api = self.futures_service.get_order_api()
        self.futures_positions_api = self.futures_service.get_positions_api()
