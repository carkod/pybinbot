"""Telegram delivery shared by synchronous trading and asynchronous analytics."""

import asyncio
from datetime import timedelta
import logging
import os
import re
import time

from dotenv import find_dotenv, load_dotenv
from requests import post
from telegram import Bot, LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TimedOut
from telegram.helpers import escape


class TelegramDelivery:
    _ALLOWED_HTML_TAGS = ("b", "strong", "i", "em", "u", "s", "code", "pre", "a")

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        *,
        min_send_interval_seconds: float = 0,
        retry_after_pad_seconds: float = 2,
    ) -> None:
        load_dotenv(find_dotenv(usecwd=True))
        self.token = os.getenv("TELEGRAM_BOT_KEY", "") if token is None else token
        self.chat_id = os.getenv("TELEGRAM_USER_ID", "") if chat_id is None else chat_id
        self.bot = Bot(token=self.token) if self.token else None
        self._send_lock = asyncio.Lock()
        self._min_send_interval_seconds = min_send_interval_seconds
        self._retry_after_pad_seconds = retry_after_pad_seconds
        self._last_send_at = 0.0

    def _sanitize_html(self, message: str) -> str:
        """
        Escape raw HTML-sensitive characters while preserving a small set of
        Telegram-supported formatting tags used by the app.
        """
        sanitized = escape(message)

        for tag in self._ALLOWED_HTML_TAGS:
            sanitized = sanitized.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            sanitized = sanitized.replace(f"&lt;/{tag}&gt;", f"</{tag}>")

        # Preserve simple attributes on pre/code tags only if they were
        # intentionally provided, e.g. <pre language="python">.
        sanitized = re.sub(
            r"&lt;(pre|code)\s+([^&]*)&gt;",
            lambda match: f"<{match.group(1)} {match.group(2)}>",
            sanitized,
        )
        sanitized = re.sub(
            r"&lt;a\s+href=(?:&#x27;|&quot;)(.+?)(?:&#x27;|&quot;)&gt;",
            lambda match: f'<a href="{match.group(1)}">',
            sanitized,
        )

        # Preserve comparison operators and other already-escaped text entities
        # provided by upstream message builders, e.g. "&lt;" in algorithm text.
        sanitized = re.sub(
            r"&amp;(lt|gt|amp|quot|#x27);",
            lambda match: f"&{match.group(1)};",
            sanitized,
        )

        return sanitized

    async def _sleep_for_send_interval(self) -> None:
        if self._min_send_interval_seconds <= 0 or self._last_send_at <= 0:
            return
        elapsed = time.monotonic() - self._last_send_at
        sleep_seconds = self._min_send_interval_seconds - elapsed
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)

    def _retry_after_seconds(self, error: RetryAfter) -> float:
        retry_after = error.retry_after
        if isinstance(retry_after, timedelta):
            return retry_after.total_seconds()
        return float(retry_after)

    async def send(self, message: str) -> bool:
        if not self.token or not self.chat_id or self.bot is None:
            return False
        async with self._send_lock:
            while True:
                await self._sleep_for_send_interval()
                try:
                    await self.bot.send_message(
                        self.chat_id,
                        text=self._sanitize_html(message),
                        parse_mode=ParseMode.HTML,
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )
                    self._last_send_at = time.monotonic()
                    return True
                except RetryAfter as e:
                    retry_after = self._retry_after_seconds(e)
                    sleep_seconds = retry_after + self._retry_after_pad_seconds
                    logging.warning(
                        "Telegram flood control active; retrying message in %.1f seconds",
                        sleep_seconds,
                    )
                    await asyncio.sleep(sleep_seconds)
                except TimedOut:
                    logging.warning("Telegram message timed out; skipping")
                    return False
                except Exception as exc:
                    logging.warning("Telegram delivery failed (%s)", type(exc).__name__)
                    return False

    def send_once(self, message: str) -> bool:
        """Attempt an ephemeral synchronous delivery, without retries or cooldowns."""
        if not self.token or not self.chat_id:
            return False
        try:
            response = post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": self._sanitize_html(message),
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                },
                timeout=2,
            )
            response.raise_for_status()
            return bool(response.json().get("ok"))
        except Exception as exc:
            # HTTP exception strings can contain the bot token in the URL.
            logging.warning("Telegram delivery failed (%s)", type(exc).__name__)
            return False
