from shared import timestamps
from datetime import datetime


def test_timestamp():
    ts = timestamps.timestamp()
    assert isinstance(ts, int)
    assert len(str(ts)) == 13


def test_round_timestamp():
    assert timestamps.round_timestamp(1747852851106) == 1747852851106
    # Extra lower-order digits are discarded to keep at most 13 digits
    assert timestamps.round_timestamp(1747852851106123) == 1747852851106
    assert timestamps.round_timestamp(1747852851) == 1747852851


def test_ts_to_day():
    ts = 1700000000  # seconds
    assert timestamps.ts_to_day(ts) == datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    ms = 1700000000000  # ms
    assert timestamps.ts_to_day(ms) == datetime.fromtimestamp(ms // 1000).strftime(
        "%Y-%m-%d"
    )


def test_ms_to_sec():
    assert timestamps.ms_to_sec(1000) == 1
    assert timestamps.ms_to_sec(1234567) == 1234


def test_sec_to_ms():
    assert timestamps.sec_to_ms(1) == 1000
    assert timestamps.sec_to_ms(1234) == 1234000


def test_ts_to_humandate():
    ms = 1747852851106
    sec = 1747852851
    assert timestamps.ts_to_humandate(ms).startswith("202")
    assert timestamps.ts_to_humandate(sec).startswith("202")
