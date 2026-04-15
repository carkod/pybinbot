from pybinbot.apis.binbot.base import BinbotApi


class TestSubmitBotEventLogs:
    def test_formats_string_payload(self) -> None:
        api = object.__new__(BinbotApi)
        api.bb_submit_errors = "https://example.com/bot/errors"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

        api.request = fake_request

        result = api.submit_bot_event_logs("bot-1", "failed to create bot")

        assert result == {"ok": True}
        assert captured["url"] == "https://example.com/bot/errors/bot-1"
        assert captured["method"] == "POST"
        assert captured["json"] == {"errors": "failed to create bot"}

    def test_formats_list_payload(self) -> None:
        api = object.__new__(BinbotApi)
        api.bb_submit_errors = "https://example.com/bot/errors"

        captured: dict = {}

        def fake_request(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

        api.request = fake_request

        result = api.submit_bot_event_logs(
            "bot-1",
            ["failed to create bot", "failed to create deal"],
        )

        assert result == {"ok": True}
        assert captured["url"] == "https://example.com/bot/errors/bot-1"
        assert captured["method"] == "POST"
        assert captured["json"] == {
            "errors": ["failed to create bot", "failed to create deal"]
        }
