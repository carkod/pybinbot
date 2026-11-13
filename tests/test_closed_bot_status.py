from pybinbot import BotBase, BotModel, BotResponse, Status


def test_closed_status_round_trips_through_bot_models_and_responses():
    assert Status("closed") is Status.closed
    candidate = BotBase(pair="BTCUSDT", status=Status.closed)
    bot = BotModel(**candidate.model_dump())
    response = BotResponse(message="Archived candidate", data=bot)
    payload = response.model_dump_json()
    restored = BotResponse.model_validate_json(payload)
    assert restored.data is not None
    assert restored.data.status == Status.closed
    assert restored.model_dump(mode="json")["data"]["status"] == "closed"
