"""تست‌های پلاگین‌های نسل پنجم: polls (نظرسنجی دکمه‌ای)، afk، posthours."""

from __future__ import annotations

from datetime import time as dtime

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
USER1 = 100
USER2 = 101


def _msg(d, chat_id, user_id, text, user_name="کاربر", user_username=""):
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        user_username=user_username,
        data={"text": text, "content_type": "text", "sender_name": user_name},
    )


# ═══ polls ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_poll_create_buttons_vote_and_results(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command(
        "/poll کدام زبان را دوست دارید؟ | پایتون | گو | جاوا",
        chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "نظرسنجی" in out[0]
    # دکمه‌های رأی ساخته شد
    assert d.last_keyboard and len(d.last_keyboard) >= 2
    data0 = d.last_keyboard[0][0]["data"]
    assert data0.startswith("poll:")

    # رأی کاربر ۱ به گزینهٔ اول
    out = await d.dispatch_callback(data0, chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "رأی شما" in out[0]

    # رأی تکراری رد می‌شود
    out = await d.dispatch_callback(data0, chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "قبلاً رأی" in out[0]

    # کاربر ۲ به گزینهٔ دوم رأی می‌دهد
    data1 = d.last_keyboard[0][1]["data"]
    await d.dispatch_callback(data1, chat_id=CHAT, user_id=USER2, lang="fa")

    out = await d.try_dispatch_command("/pollresults", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    joined = "\n".join(out)
    assert "1 رأی" in joined and "مجموع آراء: 2" in joined


@pytest.mark.asyncio
async def test_poll_close_announces_winner(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/poll تست | آری | نه", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    data0 = d.last_keyboard[0][0]["data"]
    await d.dispatch_callback(data0, chat_id=CHAT, user_id=USER1, lang="fa")
    out = await d.try_dispatch_command("/pollclose", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "برنده" in out[0] and "آری" in out[0]
    # رأی پس از بسته‌شدن
    out = await d.dispatch_callback(data0, chat_id=CHAT, user_id=USER2, lang="fa")
    assert out and ("بسته" in out[0] or "منقضی" in out[0])


@pytest.mark.asyncio
async def test_poll_admin_only(e2e):
    host, d, groups, roles, _ = e2e
    out = await d.try_dispatch_command("/poll سؤال | آ | ب", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "دسترسی ندارید" in out[0]


# ═══ afk ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_afk_set_mention_and_welcome_back(e2e):
    host, d, groups, roles, _ = e2e
    await d.try_dispatch_command("/afk در جلسه هستم", chat_id=CHAT, user_id=USER1,
                                 lang="fa", sender_name="زهرا احمدی",
                                 sender_username="zahra_a")
    # منشن توسط کاربر دیگر → اعلان
    out = await _msg(d, CHAT, USER2, "@zahra_a کجایی؟", user_name="مریم")
    assert out and "دور از دسترس" in out[0] and "در جلسه هستم" in out[0]
    # پیام خود کاربر → برداشتن
    out = await _msg(d, CHAT, USER1, "برگشتم بچه‌ها", user_name="زهرا احمدی")
    assert out and "خوش برگشتید" in out[0]
    # دیگر اعلان نیست
    out = await _msg(d, CHAT, USER2, "@zahra_a سلام", user_name="مریم")
    assert not out


@pytest.mark.asyncio
async def test_afk_mention_by_name_and_manual_off(e2e):
    host, d, groups, roles, _ = e2e
    await d.try_dispatch_command("/afk", chat_id=CHAT, user_id=USER1,
                                 lang="fa", sender_name="حسین محمدی")
    # نام کامل در متن → اعلان
    out = await _msg(d, CHAT, USER2, "حسین محمدی کجاست؟", user_name="مریم")
    assert out and "حسین محمدی" in out[0]
    # خاموش‌کردن دستی
    out = await d.try_dispatch_command("/afk off", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "برداشته شد" in out[0]
    out = await _msg(d, CHAT, USER2, "حسین محمدی کجاست؟", user_name="مریم")
    assert not out


# ═══ posthours ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_posthours_blocks_outside_window(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/posthours 08:00-22:00", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "فعال شد" in out[0]
    mod = host.records["posthours"].module
    # شب → پیام عادی حذف می‌شود
    mod._now = lambda: dtime(23, 30)
    out = await _msg(d, CHAT, USER1, "پیام شبانه", user_name="کاربر")
    assert out and "مجاز نیست" in out[0]
    assert actions and actions[-1][1]["reason"] == "posthours"
    # روز → مجاز
    mod._now = lambda: dtime(12, 0)
    actions.clear()
    out = await _msg(d, CHAT, USER1, "پیام روزانه", user_name="کاربر")
    assert not out and not actions


@pytest.mark.asyncio
async def test_posthours_staff_exempt_and_off(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, 50, "mod", by_user=OWNER)
    await d.try_dispatch_command("/posthours 08:00-22:00", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    mod = host.records["posthours"].module
    mod._now = lambda: dtime(23, 30)
    # کارکن معاف است
    await _msg(d, CHAT, 50, "پیام مدیر", user_name="مدیر میانی")
    assert not actions
    # خاموش‌کردن
    out = await d.try_dispatch_command("/posthours off", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "خاموش" in out[0]
    await _msg(d, CHAT, USER1, "پیام شبانه", user_name="کاربر")
    assert not actions


def _wire(d):
    actions: list[tuple] = []
    d.action_sink = lambda chat, a: actions.append((chat, a))
    return (actions,)
