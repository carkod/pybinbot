import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from requests import Response, HTTPError
from aiohttp import ClientResponse
from pybinbot.shared.handlers import aio_response_handler, handle_binance_errors
from pybinbot.apis.binbot.exceptions import BinbotErrors, QuantityTooLow
from pybinbot.apis.binance.exceptions import (
    BinanceErrors,
    InvalidSymbol,
    NotEnoughFunds,
)


class TestAioResponseHandler:
    """Tests for async response handler"""

    @pytest.mark.asyncio
    async def test_aio_response_handler_returns_json(self):
        """
        Test that aio_response_handler returns JSON content
        """
        mock_response = AsyncMock(spec=ClientResponse)
        mock_response.json.return_value = {"success": True, "data": "test"}

        result = await aio_response_handler(mock_response)

        assert result == {"success": True, "data": "test"}
        mock_response.json.assert_called_once()

    @pytest.mark.asyncio
    async def test_aio_response_handler_with_empty_response(self):
        """Test that aio_response_handler handles empty JSON"""
        mock_response = AsyncMock(spec=ClientResponse)
        mock_response.json.return_value = {}

        result = await aio_response_handler(mock_response)

        assert result == {}


class TestHandleBinanceErrors:
    """Tests for Binance error handler"""

    def test_successful_response(self):
        """Test handling successful response"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True, "code": 200}

        result = handle_binance_errors(mock_response)

        assert result == {"success": True, "code": 200}

    def test_logs_request_weight(self):
        """Test that request weight is logged"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {"x-mbx-used-weight-1m": "500"}
        mock_response.url = "https://api.binance.com/test"
        mock_response.json.return_value = {"success": True}

        with patch("pybinbot.shared.handlers.logging") as mock_logging:
            handle_binance_errors(mock_response)
            mock_logging.info.assert_called_once()
            assert "500" in str(mock_logging.info.call_args)

    def test_http_error_403(self):
        """Test handling 403 Cloudfront error"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 403
        mock_response.reason = "Forbidden"
        mock_response.headers = {}

        with pytest.raises(HTTPError):
            handle_binance_errors(mock_response)

    def test_http_error_404(self):
        """Test handling 404 error"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.json.return_value = {}

        with pytest.raises(HTTPError):
            handle_binance_errors(mock_response)

    def test_binance_error_invalid_quantity(self):
        """Test handling Binance invalid quantity error (-1013)"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200  # Status < 400, so it checks specific codes
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -1013,
            "message": "Invalid quantity",
            "error": -1013,
        }

        with pytest.raises(QuantityTooLow):
            handle_binance_errors(mock_response)

    def test_binance_error_not_enough_funds(self):
        """Test handling Binance insufficient balance error (-2010)"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200  # Status < 400, so it checks specific codes
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -2010,
            "msg": "Insufficient balance for requested action",
        }

        with pytest.raises(NotEnoughFunds):
            handle_binance_errors(mock_response)

    def test_binance_error_invalid_symbol(self):
        """Test handling Binance invalid symbol error (-1121)"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200  # Status < 400, so it checks specific codes
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -1121,
            "msg": "Invalid symbol",
        }

        with pytest.raises(InvalidSymbol):
            handle_binance_errors(mock_response)

    def test_binance_error_too_many_requests(self):
        """Test handling Binance too many requests error (-1003)"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200  # Status < 400, so it processes the sleep
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -1003,
            "msg": "Too many requests",
        }

        with patch("pybinbot.shared.handlers.sleep") as mock_sleep:
            result = handle_binance_errors(mock_response)
            mock_sleep.assert_called_once_with(60)
            assert result["code"] == -1003

    def test_binbot_error_response(self):
        """Test handling Binbot error response"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {
            "error": 1,
            "message": "Bot creation failed",
        }

        with pytest.raises(BinbotErrors):
            handle_binance_errors(mock_response)

    def test_generic_binance_error(self):
        """Test handling generic Binance error with code and msg"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -1000,
            "msg": "An unknown error occurred while processing the request",
        }

        with pytest.raises(BinanceErrors) as exc_info:
            handle_binance_errors(mock_response)

        assert "-1000" in str(exc_info.value)

    def test_binance_error_with_status_400(self):
        """Test that status >= 400 with msg and code raises BinanceErrors"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -1013,
            "msg": "Invalid quantity",
        }

        # When status >= 400, BinanceErrors is raised before checking specific codes
        with pytest.raises(BinanceErrors) as exc_info:
            handle_binance_errors(mock_response)

        assert "Invalid quantity" in str(exc_info.value)

    def test_rate_limit_prevention_high_weight(self):
        """Test proactive rate limit prevention when weight > 7000"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {"x-mbx-used-weight-1m": "7500"}
        mock_response.url = "https://api.binance.com/test"
        mock_response.json.return_value = {"success": True}

        with patch("pybinbot.shared.handlers.sleep") as mock_sleep:
            with patch("pybinbot.shared.handlers.logging"):
                handle_binance_errors(mock_response)
                mock_sleep.assert_called_once_with(120)

    def test_rate_limit_429_status(self):
        """Test handling 429 status code"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}

        with patch("pybinbot.shared.handlers.sleep") as mock_sleep:
            handle_binance_errors(mock_response)
            mock_sleep.assert_called_once_with(3600)

    def test_rate_limit_418_status(self):
        """Test handling 418 status code"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 418
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}

        with patch("pybinbot.shared.handlers.sleep") as mock_sleep:
            handle_binance_errors(mock_response)
            mock_sleep.assert_called_once_with(3600)

    def test_binance_error_margin_short(self):
        """Test handling Binance margin short error (-2015)"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200  # Status < 400, so it checks specific codes
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": -2015,
            "msg": "Margin operation failed",
        }

        with pytest.raises(NotEnoughFunds):
            handle_binance_errors(mock_response)

    def test_response_with_code_200(self):
        """Test that code 200 in response returns content"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "code": 200,
            "msg": "Success",
            "data": {"test": "value"},
        }

        result = handle_binance_errors(mock_response)

        assert result["code"] == 200
        assert result["data"] == {"test": "value"}

    def test_403_without_reason(self):
        """Test handling 403 without reason doesn't raise HTTPError"""
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 403
        mock_response.reason = None
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}

        result = handle_binance_errors(mock_response)

        assert result == {"success": True}
