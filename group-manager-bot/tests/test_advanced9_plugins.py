"""تست‌های پلاگین‌های نسل نهم (۷ پلاگین): faq، joinlog، safemode،
botprotect، karma، timednote، mediafocus."""

from __future__ import annotations

import time

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
USER1 = 100
USER2 = 101
BOTX = 5550001
CHANNEL = -100987


def _wire(host, d):
    actions: list[tuple] = []
    audit: list[tuple] = []
    outbox: list[tuple] = []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    host.out_sink = lambda chat, text: outbox.append((chat, text))
    d.action_sink = host.action_sink
    return actions, audit, outbox


def _msg(d, chat_id, user_id, text, content_type="text", user_name="کاربر"):
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id,
        user_name=user_name,
        data={"text": text, "content_type": content_type,
              "sender_name": user_name, "skip_flood": True},
    )


def _join(d, user_id, name="تازه", username="", bot=False):
    return d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=user_id,
        user_name=name, user_username=username,
        data={"member_id": user_id, "member_name": name,
              "member_username": username, "member_bot": bot,
              "chat_title": "گروه آزمایش", "member_count": 1},
    )


def _leave(d, user_id, name="تازه", username=""):
    return d.dispatch_event(
        "member_left", chat_id=CHAT, lang="fa", user_id=user_id,
        user_name=name, user_username=username,
        data={"member_id": user_id, "member_name": name,
              "member_username": username, "chat_title": "گروه آزمایش"},
    )


# ═══ faq ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_faq_add_list_answer_delete(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # افزودن دو پرسش
    out = await d.try_dispatch_command(
        "/faqadd ساعت کاری گروه چیست؟ => از ۹ صبح تا ۹ شب", chat_id=CHAT,
        user_id=ADMIN, lang="fa")
    assert out and "ثبت شد" in out[0]
    out = await d.try_dispatch_command(
        "/faqadd آدرس گروه چیست؟ => همین لینک دعوت", chat_id=CHAT,
        user_id=ADMIN, lang="fa")
    assert out and "ثبت شد" in out[0]
    # پرسش تکراری رد می‌شود
    out = await d.try_dispatch_command(
        "/faqadd ساعت کاری گروه چیست؟ => دوباره", chat_id=CHAT,
        user_id=ADMIN, lang="fa")
    assert out and "قبلاً" in out[0]
    # فهرست دکمه‌ای برای کاربر عادی
    out = await d.try_dispatch_command("/faq", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "پرسش‌های پرتکرار" in out[0]
    assert d.last_keyboard
    first_data = d.last_keyboard[0][0]["data"]
    assert first_data.startswith("faq:")
    # کلیک روی پرسش اول → پاسخ
    out = await d.dispatch_callback(first_data, chat_id=CHAT, user_id=USER1,
                                    lang="fa")
    assert out and "۹ صبح" in out[0]
    # حذف پرسش اول
    await d.try_dispatch_command("/faqdel", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    out = await d.try_dispatch_command("/faqdel 1", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "حذف شد" in out[0]
    out = await d.try_dispatch_command("/faqdel all", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "همهٔ پرسش" in out[0]


# ═══ joinlog ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_joinlog_to_group_and_channel(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/joinlog on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    # بدون کانال → خط به خودِ گروه
    await _join(d, 777, "مریم", username="maryam")
    assert any("ورود: مریم" in t for _, t in outbox)
    await _leave(d, 777, "مریم", username="maryam")
    assert any("خروج: مریم" in t for _, t in outbox)
    # با کانال → خط به کانال
    outbox.clear()
    await d.try_dispatch_command("/setjoinlog -100987", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    await _join(d, 778, "رضا")
    assert any(cid == CHANNEL and "رضا" in t for cid, t in outbox)


# ═══ safemode ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_safemode_snapshot_and_restore(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # وضعیت اولیه: captcha_on خاموشِ صریح، caps_on روشن، بقیه غایب
    from bot.repositories.base import Group
    g = groups.get(CHAT) or Group(chat_id=CHAT, settings={})
    g.settings["captcha_on"] = False
    g.settings["caps_on"] = True
    groups.upsert(g)
    out = await d.try_dispatch_command("/safemode on", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "محافظت روشن شد" in out[0]
    g = groups.get(CHAT)
    assert g.settings["captcha_on"] is True
    assert g.settings["caps_on"] is True
    assert g.settings["automod_on"] is True
    assert g.settings["mf_on"] is True
    # خاموش → بازگردانی دقیق
    out = await d.try_dispatch_command("/safemode off", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "بازگردانی شد" in out[0]
    g = groups.get(CHAT)
    assert g.settings["captcha_on"] is False
    assert g.settings["caps_on"] is True
    assert "mf_on" not in g.settings


# ═══ botprotect ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_botprotect_bans_unknown_keeps_whitelist(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/botprotect on", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    # ربات ناآشنا → بن خودکار
    await _join(d, BOTX, "ربات اسپم", bot=True)
    assert any(a[1].get("type") == "ban" and
               a[1].get("reason") == "botprotect" for a in actions)
    assert any("خودکار: بن" in ln for _, lines in audit for ln in lines)
    # ربات لیست سفید → معاف
    actions.clear()
    await d.try_dispatch_command(f"/botprotect allow {BOTX + 1}",
                                 chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _join(d, BOTX + 1, "ربات معتبر", bot=True)
    assert not actions
    # کاربر عادی (غیر ربات) دست نمی‌خورد
    await _join(d, 777, "علی")
    assert not actions


# ═══ karma ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_karma_give_top_and_limits(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # امتیاز به خود ممنوع
    out = await d.try_dispatch_command(f"/karma {USER1}", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "خودتان" in out[0]
    # به کارمند ممنوع
    out = await d.try_dispatch_command(f"/karma {ADMIN}", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "مدیران" in out[0]
    # امتیاز موفق به USER2
    out = await d.try_dispatch_command(f"/karma {USER2}", chat_id=CHAT,
                                       user_id=USER1, lang="fa",
                                       sender_name="علی")
    assert out and "مجموع: 1" in out[0]
    # تکرار در ۲۴ ساعت رد (کول‌داون کوتاه را پاک می‌کنیم تا به سقف روزانه برسیم)
    host.cache.delete(f"karma:cool:{CHAT}:{USER1}")
    out = await d.try_dispatch_command(f"/karma {USER2}", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "۲۴ ساعت" in out[0]
    # امتیاز خود کاربر
    out = await d.try_dispatch_command("/karma", chat_id=CHAT, user_id=USER2,
                                       lang="fa")
    assert out and "امتیاز شما: 1" in out[0]
    # برترین‌ها
    out = await d.try_dispatch_command("/karmatop", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "برترین‌های گروه" in out[0]


# ═══ timednote ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_timednote_delivers_on_tick(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/timednote 2h جلسهٔ هماهنگی ساعت ۶",
                                       chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "ثبت شد" in out[0]
    mod = host.records["timednote"].module
    job = mod._jobs[CHAT][0]
    assert job["text"] == "جلسهٔ هماهنگی ساعت ۶"
    # فهرست
    out = await d.try_dispatch_command("/timednotes", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "جلسهٔ هماهنگی" in out[0]
    # سررسید کن و تیک بزن
    job["due_at"] = time.monotonic() - 1
    await host.tick()
    assert any("جلسهٔ هماهنگی" in t for _, t in outbox)
    assert CHAT not in mod._jobs


# ═══ mediafocus ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_mediafocus_blocks_text_allows_media(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/mediafocus on", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    # رسانه مجاز است
    await _msg(d, CHAT, USER1, "", content_type="photo")
    assert not actions
    # متن بدون رسانه → حذف
    out = await _msg(d, CHAT, USER1, "سلام به همه", content_type="text")
    assert out and "فقط رسانه" in out[0]
    assert any(a[1].get("reason") == "mediafocus" for a in actions)
    # کپشن ممنوع (پس از پاک کردن کول‌داون هشدار)
    actions.clear()
    mod = host.records["mediafocus"].module
    mod._last_warn.clear()
    await d.try_dispatch_command("/mediafocus caption off", chat_id=CHAT,
                                 user_id=ADMIN, lang="fa")
    out = await _msg(d, CHAT, USER1, "کپشن مزاحم", content_type="photo")
    assert out and "کپشن" in out[0]
    assert any(a[1].get("reason") == "mediafocus" for a in actions)
    # کارکن معاف‌اند
    actions.clear()
    roles.set_role(CHAT, ADMIN + 1, "admin", by_user=OWNER)
    await _msg(d, CHAT, ADMIN + 1, "اعلامیهٔ متنی مدیر", content_type="text")
    assert not actions
