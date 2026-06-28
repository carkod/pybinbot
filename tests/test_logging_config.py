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
    assert logging.getLogger("uvicorn").level == logging.WARNING
    assert logging.getLogger("uvicorn.error").level == logging.WARNING
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


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


def test_configure_logging_overrides_uvicorn_child_logger_levels(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    monkeypatch.delenv("QUIET_LIB_LOG_LEVEL", raising=False)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    configure_logging(force=True)

    assert logging.getLogger("uvicorn.error").level == logging.ERROR
    assert logging.getLogger("uvicorn.access").level == logging.ERROR
