"""تست‌های bot/domain/channel.py — شناسهٔ کانال (دامنهٔ خالص)."""

from __future__ import annotations

from bot.domain.channel import parse_channel_id


def test_parse_channel_id_numeric():
    assert parse_channel_id("-1001234567890") == -1001234567890
    assert parse_channel_id("1001234567890") == 1001234567890
    assert parse_channel_id(12345) == 12345


def test_parse_channel_id_invalid():
    assert parse_channel_id("") is None
    assert parse_channel_id(None) is None
    assert parse_channel_id("  ") is None
    assert parse_channel_id("@mychannel") is None
    assert parse_channel_id("12ab") is None
