import logging
from time import sleep
from typing import Any
from requests import Response, HTTPError
from aiohttp import ClientResponse
from pybinbot.apis.binbot.exceptions import (
    BinbotErrors,
    QuantityTooLow,
)
from pybinbot.apis.binance.exceptions import (
    BinanceErrors,
    InvalidSymbol,
    NotEnoughFunds,
)

BODY_PREVIEW_CHARS = 1000


def _log_binbot_response(response: Response, message: str) -> None:
    logging.warning(
        "%s status=%s reason=%r content_type=%r url=%s body=%r",
        message,
        response.status_code,
        response.reason,
        response.headers.get("content-type"),
        response.url,
        response.text[:BODY_PREVIEW_CHARS],
    )


async def aio_response_handler(response: ClientResponse):
    content = await response.json()
    return content


def handle_binance_errors(response: Response) -> dict[Any, Any]:
    """
    Handles:
    - HTTP codes, not authorized, rate limits...
    - Bad request errors, binance internal e.g. {"code": -1013, "msg": "Invalid quantity"}
    - Binbot internal errors - bot errors, returns "errored"

    """

    if "x-mbx-used-weight-1m" in response.headers:
        logging.info(
            f"Request to {response.url} weight: {response.headers.get('x-mbx-used-weight-1m')}"
        )
    # Binance doesn't seem to reach 418 or 429 even after 2000 weight requests
    if (
        response.headers.get("x-mbx-used-weight-1m")
        and float(response.headers.get("x-mbx-used-weight-1m", 0)) > 7000
    ):
        logging.warning("Request weight limit prevention pause, waiting 1 min")
        sleep(120)

    if response.status_code == 418 or response.status_code == 429:
        logging.warning("Request weight limit hit, ban will come soon, waiting 1 hour")
        sleep(3600)

    # Cloudfront 403 error
    if response.status_code == 403 and response.reason:
        raise HTTPError(response=response)

    content = response.json()

    if response.status_code == 404:
        raise HTTPError(response=response)

    # Show error messsage for bad requests
    if response.status_code >= 400:
        # Binance errors
        if "msg" in content and "code" in content:
            raise BinanceErrors(content["msg"], content["code"])

        # Binbot errors
        if content and "error" in content and content["error"] == 1:
            raise BinbotErrors(content["message"], content["error"])

    # Binance errors
    if content and "code" in content:
        if content["code"] == -1013:
            raise QuantityTooLow(content["message"], content["error"])
        if content["code"] == 200:
            return content
        if (
            content["code"] == -2010
            or content["code"] == -1013
            or content["code"] == -2015
        ):
            # Not enough funds. Ignore, send to bot errors
            # Need to be dealt with at higher levels
            raise NotEnoughFunds(content["msg"], content["code"])

        if content["code"] == -1003:
            # Too many requests, most likely exceeded API rate limits
            # Back off for > 5 minutes, which is Binance's ban time
            print("Too many requests. Back off for 1 min...")
            sleep(60)

        if content["code"] == -1121:
            raise InvalidSymbol(f"Binance error: {content['msg']}", content["code"])

    return content


def handle_binbot_errors(response: Response) -> dict[Any, Any]:
    """
    Handles:
    - HTTP codes, not authorized, rate limits...
    - Bad request errors, binance internal e.g. {"code": -1013, "msg": "Invalid quantity"}
    - Binbot internal errors - bot errors, returns "errored"

    """
    if response.status_code == 404:
        _log_binbot_response(response, "Binbot API returned 404")
        raise HTTPError(response=response)

    try:
        content = response.json()
    except Exception:
        _log_binbot_response(response, "Binbot API returned non-JSON response")
        raise

    if response.status_code == 401:
        if "detail" in content:
            raise BinbotErrors(msg=content["detail"])

    # Show error messsage for bad requests
    if response.status_code >= 400:
        # Binbot errors
        if content and "error" in content and content["error"] == 1:
            raise BinbotErrors(content["message"], content["error"])

    return content
