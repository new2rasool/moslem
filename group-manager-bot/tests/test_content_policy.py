"""تست‌های دامنهٔ سیاست محتوا — domain/content_policy.py (خالص)"""

from bot.domain.content_policy import (
    LOCKABLE,
    check_message,
    extract_domains,
    has_url,
    is_whitelisted,
)


def test_has_url_detection():
    assert has_url("https://example.com/x") is True
    assert has_url("www.example.com") is True
    assert has_url("t.me/my_channel") is True
    assert has_url("telegram.me/joinchat/abc") is True
    assert has_url("no links here") is False
    assert has_url("example dot com") is False


def test_extract_domains():
    assert extract_domains("go to example.com and Test.ORG") == {"example.com", "test.org"}


def test_whitelist():
    assert is_whitelisted("https://github.com/a", ["github.com"]) is True
    assert is_whitelisted("https://github.com/a https://evil.io", ["github.com"]) is False
    assert is_whitelisted("no link", ["github.com"]) is False  # لینکی نیست
    # زیردامنه هم مجاز است
    assert is_whitelisted("https://sub.github.com/a", ["github.com"]) is True


def test_check_url_violation():
    assert check_message(content_type="text", text="buy at https://spam.io",
                         is_forward=False, locks={"url": "delete"}) == "url"


def test_check_url_whitelisted_ok():
    assert check_message(content_type="text", text="https://github.com/ok",
                         is_forward=False, locks={"url": "delete"},
                         url_whitelist=["github.com"]) is None


def test_check_forward_violation():
    assert check_message(content_type="text", text="hello", is_forward=True,
                         locks={"forward": "delete"}) == "forward"


def test_check_media_violation():
    assert check_message(content_type="photo", text="", is_forward=False,
                         locks={"photos": "delete"}) == "photos"
    assert check_message(content_type="video", is_forward=False,
                         locks={"videos": "delete"}) == "videos"
    assert check_message(content_type="document", is_forward=False,
                         locks={"documents": "warn"}) == "documents"
    assert check_message(content_type="sticker", is_forward=False,
                         locks={"photos": "delete"}) is None  # قفلِ ناربط


def test_priority_url_over_forward():
    # پیام فورواردیِ لینک‌دار → url اولویت دارد
    assert check_message(content_type="text", text="https://x.io", is_forward=True,
                         locks={"url": "delete", "forward": "delete"}) == "url"


def test_locks_empty_or_invalid_ignored():
    assert check_message(content_type="photo", is_forward=False, locks={}) is None
    assert check_message(content_type="photo", is_forward=False,
                         locks={"photos": ""}) is None  # اکشن خالی = خاموش
    assert check_message(content_type="photo", is_forward=False,
                         locks={"photos": "bogus"}) is None


def test_lockable_set_sane():
    assert {"url", "forward", "photos", "videos", "gifs", "stickers"} <= LOCKABLE
