"""تست‌های پلاگین‌های نسل هشتم (۷ پلاگین): votekick، lottery، digest،
autorole، mediaflood، nameguard، backup."""

from __future__ import annotations

import json
import time

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
USER1 = 100
V1, V2, V3 = 101, 102, 103
SPAM = 555


def _wire(host, d):
    actions: list[tuple] = []
    audit: list[tuple] = []
    outbox: list[tuple] = []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    host.out_sink = lambda chat, text: outbox.append((chat, text))
    d.action_sink = host.action_sink
    return actions, audit, outbox


def _msg(d, chat_id, user_id, text, user_name="کاربر", content_type="text"):
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        data={"text": text, "content_type": content_type, "sender_name": user_name,
              "skip_flood": True},
    )


def _join(d, user_id, name="تازه", username=""):
    return d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=user_id, user_name=name,
        user_username=username,
        data={"member_id": user_id, "member_name": name,
              "member_username": username},
    )


# ═══ votekick ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_votekick_passes_and_kicks(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/setvotekick 2", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    out = await d.try_dispatch_command("/votekick 555 اسپم", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "رأی‌گیری" in out[0]
    data_y = d.last_keyboard[0][0]["data"]
    # رأی موافق توسط دو عضو
    for uid in (V1, V2):
        await d.dispatch_callback(data_y, chat_id=CHAT, user_id=uid, lang="fa")
    # پایان مهلت → شمارش
    mod = host.records["votekick"].module
    mod._votes[CHAT]["deadline"] = 0.0
    await host.tick()
    assert CHAT not in mod._votes
    # اکشن اخراج + اطلاع‌رسانی + ردیف حسابرسی
    assert any(a[1].get("type") == "kick" and "votekick" in a[1].get("reason", "")
               for a in actions)
    assert outbox and "به نتیجه رسید" in outbox[-1][1]


@pytest.mark.asyncio
async def test_votekick_guards(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, 50, "mod", by_user=OWNER)
    # هدفِ کارکن ممنوع
    out = await d.try_dispatch_command("/votekick 50 چرا", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "مدیران" in out[0]
    # آغازکننده نمی‌تواند رأی بدهد
    out = await d.try_dispatch_command("/votekick 555 اسپم", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    data_y = d.last_keyboard[0][0]["data"]
    out = await d.dispatch_callback(data_y, chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "آغازکننده" in out[0]
    # رأی تکراری رد می‌شود
    await d.dispatch_callback(data_y, chat_id=CHAT, user_id=V1, lang="fa")
    out = await d.dispatch_callback(data_y, chat_id=CHAT, user_id=V1, lang="fa")
    assert out and "قبلاً رأی" in out[0]


# ═══ lottery ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lottery_join_and_winner(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/lottery start", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "قرعه" in out[0]
    data = d.last_keyboard[0][0]["data"]
    # فقط یک شرکت‌کننده → برندهٔ قطعی همان است
    await d.dispatch_callback(data, chat_id=CHAT, user_id=USER1, lang="fa",
                              sender_name="علی")
    out = await d.dispatch_callback(data, chat_id=CHAT, user_id=USER1, lang="fa",
                                    sender_name="علی")
    assert out and "قبلاً" in out[0]
    out = await d.try_dispatch_command("/lottery end", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "علی" in out[0] and "100" in out[0]
    # قرعه‌کشی تمام شد
    mod = host.records["lottery"].module
    assert CHAT not in mod._lotteries


@pytest.mark.asyncio
async def test_lottery_cancel(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/lottery start", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    out = await d.try_dispatch_command("/lottery cancel", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "لغو شد" in out[0]


# ═══ digest ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_digest_periodic_report(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # یک اکشن ثبت کن تا در گزارش دیده شود
    api = host.records["ping"].api
    await api.record_action(CHAT, "warn", SPAM, ADMIN, reason="تست")
    out = await d.try_dispatch_command("/digest 30", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "روشن شد" in out[0]
    mod = host.records["digest"].module
    import time as _t
    job = mod._jobs[CHAT]
    job["last_sent"] = _t.monotonic() - job["interval_s"]  # همین حالا سررسید شود
    await _join(d, 777, "تازه")
    await host.tick()
    reports = [t for _, t in outbox if "گزارش" in t]
    assert reports, f"گزارش دوره‌ای نیامد: {outbox}"
    assert "1" in reports[-1]  # یک اکشنِ امروز
    # خاموش‌کردن
    out = await d.try_dispatch_command("/digest off", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "خاموش" in out[0]
    assert CHAT not in mod._jobs


# ═══ autorole ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_autorole_promotes_after_threshold(e2e):
    host, d, groups, roles, _ = e2e
    _, audit, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/autorole on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    await d.try_dispatch_command("/setautorole 5 mod", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    for i in range(5):
        out = await _msg(d, CHAT, USER1, f"پیام فعالانه {i}", user_name="علی")
    assert roles.get_role(CHAT, USER1) == "mod"
    # ردیف حسابرسی با برچسب «خودکار: ارتقا»
    assert any("ارتقا" in ln for _, lines in audit for ln in lines)
    assert any("خودکار" in ln for _, lines in audit for ln in lines)
    # دیگر تکرار نمی‌شود (همان نقش مانده)
    await _msg(d, CHAT, USER1, "پیام چهارم دیگر", user_name="علی")
    assert roles.get_role(CHAT, USER1) == "mod"


# ═══ mediaflood ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_mediaflood_deletes_after_limit(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/mediaflood on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    await d.try_dispatch_command("/setmediaflood 3 60", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    # سه رسانه مجاز
    for _ in range(3):
        await _msg(d, CHAT, USER1, "", content_type="photo")
    assert not actions
    # رسانهٔ چهارم → حذف + هشدار
    out = await _msg(d, CHAT, USER1, "", content_type="photo")
    assert out and "سیل رسانه" in out[0]
    assert any(a[1].get("reason") == "mediaflood" for a in actions)


# ═══ nameguard ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_nameguard_kicks_link_name(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/nameguard on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    out = await _join(d, 3001, "خرید ویلا https://example.com/lux")
    assert out and "اخراج شد" in out[0]
    assert any(a[1].get("type") == "kick" and
               a[1].get("reason", "").startswith("nameguard:") for a in actions)
    assert any("nameguard:url" in ln for _, lines in audit for ln in lines)
    # نام عادی مشکلی ندارد
    actions.clear()
    await _join(d, 3002, "رضا محمدی")
    assert not actions


# ═══ backup ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backup_and_restore(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # چند تنظیم
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    await d.try_dispatch_command("/setlog -10012345", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    # پشتیبان‌گیری
    out = await d.try_dispatch_command("/backup", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    assert out and "پشتیبان" in out[0]
    cached = host.cache.get(f"backup:{CHAT}")
    assert cached and '"captcha_on": true' in cached

    # تغییر وضعیت
    await d.try_dispatch_command("/captcha off", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    g = groups.get(CHAT)
    assert g.settings.get("captcha_on") is False

    # بازیابی از نسخهٔ کش
    out = await d.try_dispatch_command("/restore", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    assert out and "بازیابی شد" in out[0]
    g = groups.get(CHAT)
    assert g.settings.get("captcha_on") is True
    assert g.settings.get("log_channel") == "-10012345"
