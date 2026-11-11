from unittest.mock import AsyncMock, patch

import pytest
from telegram.error import RetryAfter

from pybinbot.shared.telegram_delivery import TelegramDelivery


@pytest.mark.parametrize(
    "message,expected",
    [
        (
            "<strong>Signal</strong> ratio <= 0.45 and >= 0.55",
            "<strong>Signal</strong> ratio &lt;= 0.45 and &gt;= 0.55",
        ),
        ("RSI (14) &lt; 30 and MACD &gt; -1", "RSI (14) &lt; 30 and MACD &gt; -1"),
        (
            "<a href='https://example.com/bots/123'>Dashboard</a>",
            '<a href="https://example.com/bots/123">Dashboard</a>',
        ),
    ],
)
def test_delivery_preserves_supported_html_and_escapes_comparisons(message, expected):
    delivery = TelegramDelivery(token="", chat_id="")
    assert delivery._sanitize_html(message) == expected


def test_initialization_loads_local_dotenv_without_overriding_environment(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_KEY", "")
    monkeypatch.delenv("TELEGRAM_BOT_KEY", raising=False)
    monkeypatch.setenv("TELEGRAM_USER_ID", "environment-chat")
    (tmp_path / ".env").write_text(
        'TELEGRAM_BOT_KEY="dotenv-token"\nTELEGRAM_USER_ID="dotenv-chat"\n'
    )
    with patch("pybinbot.shared.telegram_delivery.Bot"):
        delivery = TelegramDelivery()
    assert delivery.token == "dotenv-token"
    assert delivery.chat_id == "environment-chat"


def test_ephemeral_delivery_sends_each_attempt_without_cooldown():
    with (
        patch("pybinbot.shared.telegram_delivery.Bot"),
        patch("pybinbot.shared.telegram_delivery.post") as post,
    ):
        post.return_value.json.return_value = {"ok": True}
        delivery = TelegramDelivery(token="test-token", chat_id="test-chat")
        message = "<strong>Bot</strong> #BTCUSDTM\nStop loss condition hit @ 98"
        assert delivery.send_once(message) is True
        assert delivery.send_once(message) is True
    assert post.call_count == 2
    assert post.call_args.kwargs == {
        "json": {
            "chat_id": "test-chat",
            "text": message,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        },
        "timeout": 2,
    }


@pytest.mark.asyncio
async def test_async_delivery_preserves_links_and_disables_previews():
    with patch("pybinbot.shared.telegram_delivery.Bot") as bot:
        bot.return_value.send_message = AsyncMock()
        delivery = TelegramDelivery(token="test-token", chat_id="test-chat")
        message = '<a href="https://example.com">Dashboard</a>'
        assert await delivery.send(message) is True
    bot.return_value.send_message.assert_awaited_once()
    kwargs = bot.return_value.send_message.await_args.kwargs
    assert kwargs["text"] == message
    assert kwargs["link_preview_options"].is_disabled is True


@pytest.mark.asyncio
async def test_async_delivery_keeps_binquant_flood_control_retry():
    with patch("pybinbot.shared.telegram_delivery.Bot") as bot:
        bot.return_value.send_message = AsyncMock(side_effect=[RetryAfter(0), None])
        delivery = TelegramDelivery(
            token="test-token", chat_id="test-chat", retry_after_pad_seconds=0
        )
        assert await delivery.send("Signal") is True
    assert bot.return_value.send_message.await_count == 2
