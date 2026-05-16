import logging

from pybinbot.shared.logging_config import configure_logging


def test_configure_logging_uses_env_level_for_http_and_telegram_loggers(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.delenv("QUIET_LIB_LOG_LEVEL", raising=False)

    configure_logging(force=True)

    assert logging.getLogger().level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("telegram").level == logging.WARNING
    assert logging.getLogger("telegram.ext").level == logging.WARNING


def test_configure_logging_inherits_info_level_for_dependency_loggers(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.delenv("QUIET_LIB_LOG_LEVEL", raising=False)

    configure_logging(force=True)

    assert logging.getLogger().level == logging.INFO
    assert logging.getLogger("httpx").level == logging.INFO


def test_configure_logging_allows_quiet_logger_level_override(monkeypatch):
    monkeypatch.setenv("QUIET_LIB_LOG_LEVEL", "ERROR")

    configure_logging(level="INFO", quiet_loggers=("httpx",), force=True)

    assert logging.getLogger().level == logging.INFO
    assert logging.getLogger("httpx").level == logging.ERROR
