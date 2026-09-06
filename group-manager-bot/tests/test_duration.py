"""تست‌های مدت‌زمان — domain/duration.py"""

import pytest

from bot.domain.duration import DurationError, format_duration, parse_duration


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1d6h30m", 86400 + 21600 + 1800),  # 109800
        ("2d", 172800),
        ("10m", 600),
        ("1h30m", 5400),
        ("90", 5400),  # بدون واحد = دقیقه
        ("30s", 30),
        ("1w", 604800),
        ("1w1d", 691200),
        ("1d 6h 30m", 109800),  # فاصله مجاز
        (" 5m ", 300),
        ("1h0m", 3600),
        ("1.5h", 5400),  # اعشار مجاز
    ],
)
def test_parse_valid(raw, expected):
    assert parse_duration(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "1x", "1d6x", "-5m", "0", "0s", "m", "1d6h30m extra"],
)
def test_parse_invalid(raw):
    with pytest.raises(DurationError):
        parse_duration(raw)


def test_format_duration():
    assert format_duration(109800) == "1d 6h 30m"
    assert format_duration(172800) == "2d"
    assert format_duration(5400) == "1h 30m"
    assert format_duration(30) == "30s"
    assert format_duration(0) == "0s"


def test_roundtrip():
    for raw in ("1d6h30m", "2w", "45m", "90s", "1h"):
        seconds = parse_duration(raw)
        assert parse_duration(format_duration(seconds)) == seconds
