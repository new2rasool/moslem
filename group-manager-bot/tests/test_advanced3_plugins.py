"""تست‌های پلاگین‌های نسل سوم پیشرفته: levels (XP)، stats (آمار)، notes (یادداشت)."""

from __future__ import annotations

import time

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
MOD = 11
USER1 = 100
USER2 = 101
USER3 = 102

LONG_TEXT = "پیام آزمایشی برای دریافت امتیاز " * 10  # ~۳۲۰ نویسه → ۹ XP
XP_MAX_TEXT = "متن طولانی برای سنجش سطح‌بندی ربات گروه " * 40  # ~۱٬۲۰۰ نویسه → ۱۵ XP


def _msg(d, chat_id, user_id, text, content_type="text", user_name="کاربر",
        skip_flood=False):
    data = {"text": text, "content_type": content_type, "sender_name": user_name}
    if skip_flood:
        data["skip_flood"] = True
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        data=data,
    )


def _g(d, chat_id, user_id, user_name):
    return d.dispatch_event(
        "member_joined", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        data={"member_id": user_id, "member_name": user_name},
    )


# ═══ levels ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_xp_awarded_on_text(e2e):
    host, d, *_ = e2e
    out = await _msg(d, CHAT, USER1, LONG_TEXT, user_name="علی")
    mod = host.records["levels"].module
    rec = mod._xp[CHAT][USER1]
    assert rec["xp"] >= 5
    assert rec["name"] == "علی"
    assert not out  # بدون اعلام (سطح ۱)


@pytest.mark.asyncio
async def test_xp_media_award(e2e):
    host, d, *_ = e2e
    await _msg(d, CHAT, USER1, "", content_type="photo", user_name="علی")
    mod = host.records["levels"].module
    assert mod._xp[CHAT][USER1]["xp"] == 3


@pytest.mark.asyncio
async def test_xp_cooldown_blocks_second(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # مهلت ۱۰۰۰ ثانیه → پیام دوم همان کاربر نباید امتیاز بیاورد
    await d.try_dispatch_command("/xpcooldown 1000", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, CHAT, USER1, LONG_TEXT, user_name="علی")
    mod = host.records["levels"].module
    first = mod._xp[CHAT][USER1]["xp"]
    await _msg(d, CHAT, USER1, LONG_TEXT + " بیشتر", user_name="علی")
    assert mod._xp[CHAT][USER1]["xp"] == first


@pytest.mark.asyncio
async def test_level_up_announcement(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/xpcooldown 0", chat_id=CHAT, user_id=ADMIN, lang="fa")
    # هر پیام ۱۵ XP؛ سطح ۲ پس از ۱۰۰ XP → پیام هفتم (۱۵×۷=۱۰۵)
    announced = None
    for _ in range(7):
        out = await _msg(d, CHAT, USER1, XP_MAX_TEXT, user_name="علی", skip_flood=True)
        if out:
            announced = out
    assert announced and "سطح 2" in announced[0]


@pytest.mark.asyncio
async def test_rank_self_and_admin_exempt(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await _msg(d, CHAT, USER1, LONG_TEXT, user_name="علی")
    # ادمین امتیاز نمی‌گیرد
    await _msg(d, CHAT, ADMIN, LONG_TEXT, user_name="ادمین")
    mod = host.records["levels"].module
    assert ADMIN not in mod._xp[CHAT]

    out = await d.try_dispatch_command("/rank", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "علی" in out[0] and "XP" in out[0]


@pytest.mark.asyncio
async def test_top_sorted(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/xpcooldown 0", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, CHAT, USER1, LONG_TEXT, user_name="علی", skip_flood=True)   # ۹
    await _msg(d, CHAT, USER2, LONG_TEXT, user_name="مریم", skip_flood=True)  # ۹
    await _msg(d, CHAT, USER2, LONG_TEXT, user_name="مریم", skip_flood=True)  # +۹ = ۱۸
    out = await d.try_dispatch_command("/top", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "مریم" in out[0]
    # مریم (۱۸) بالاتر از علی (۹)
    assert out[0].index("مریم") < out[0].index("علی")


@pytest.mark.asyncio
async def test_levels_disable(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/levels off", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, CHAT, USER1, LONG_TEXT, user_name="علی")
    mod = host.records["levels"].module
    assert CHAT not in mod._xp


# ═══ stats ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_stats_counts_messages_and_join(e2e):
    host, d, *_ = e2e
    await _msg(d, CHAT, USER1, "سلام", user_name="علی")
    await _msg(d, CHAT, USER2, "درود", user_name="مریم")
    await _msg(d, CHAT, USER3, "عکس", content_type="photo", user_name="حسن")
    await _g(d, CHAT, 500, "تازه")
    out = await d.try_dispatch_command("/stats", chat_id=CHAT, user_id=USER1, lang="fa")
    joined = "\n".join(out)
    assert "3" in joined  # سه پیام
    assert "امروز" in joined
    # عکس شمرده شد (نوع عکس در خط نوع‌ها)
    assert "عکس 1" in joined
    # برترین‌های امروز شامل هر سه
    assert "علی" in joined and "مریم" in joined


@pytest.mark.asyncio
async def test_stats_reset(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await _msg(d, CHAT, USER1, "سلام", user_name="علی")
    await d.try_dispatch_command("/resetstats", chat_id=CHAT, user_id=ADMIN, lang="fa")
    mod = host.records["stats"].module
    assert CHAT not in mod._STATS


# ═══ notes ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_note_save_trigger_and_list(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command(
        "/savenote قوانین گروه را از این لینک ببینید: t.me/joinchat/abc",
        chat_id=CHAT, user_id=ADMIN, lang="fa")
    # تریگر توسط کاربر عادی
    out = await _msg(d, CHAT, USER1, "#قوانین را ببینید", user_name="علی")
    assert out and "t.me/joinchat" in out[0]
    # فهرست
    out = await d.try_dispatch_command("/notes", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "#قوانین" in out[0]


@pytest.mark.asyncio
async def test_note_unknown_tag_no_reply(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/savenote فقط متن تست", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await _msg(d, CHAT, USER1, "#ناشناخته", user_name="علی")
    assert not out


@pytest.mark.asyncio
async def test_note_admin_only_save(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/savenote ممنوع متن", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "ادمین" in out[0]
    out = await d.try_dispatch_command("/notes", chat_id=CHAT, user_id=USER1, lang="fa")
    assert "ممنوع" not in out[0]


@pytest.mark.asyncio
async def test_note_delete(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/savenote قابل حذف", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/delnote قابل", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/notes", chat_id=CHAT, user_id=USER1, lang="fa")
    assert "قابل" not in out[0]


@pytest.mark.asyncio
async def test_note_normalized_trigger(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # نام با فاصلهٔ کشیده ذخیره شد ولی باید با #قانون پیدا شود
    await d.try_dispatch_command("/savenote قــانون متن قوانین", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await _msg(d, CHAT, USER1, "#قانون چیست؟", user_name="علی")
    assert out and "متن قوانین" in out[0]
