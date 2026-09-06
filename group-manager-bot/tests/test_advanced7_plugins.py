"""تست‌های پلاگین‌های نسل هفتم (۷ پلاگین): security، reportops، announcer،
trivia، capsguard، reminder، status."""

from __future__ import annotations

import time

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
USER1 = 100
USER2 = 101
NEW = 777


def _wire(host, d):
    actions: list[tuple] = []
    audit: list[tuple] = []
    outbox: list[tuple] = []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    host.out_sink = lambda chat, text: outbox.append((chat, text))
    d.action_sink = host.action_sink
    return actions, audit, outbox


def _msg(d, chat_id, user_id, text, user_name="کاربر"):
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        data={"text": text, "content_type": "text", "sender_name": user_name},
    )


# ═══ security ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_security_report_and_toggle(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/security", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    joined = "\n".join(out)
    assert "کپچای ورود" in joined and "ضد سیل" in joined

    out = await d.try_dispatch_command("/security captcha on", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "کپچای ورود" in out[0] and "روشن" in out[0]
    # کلید در تنظیمات گروه ذخیره شد
    g = groups.get(CHAT)
    assert g.settings.get("captcha_on") is True
    # گزارش بعدی وضعیت سبز را نشان می‌دهد
    out = await d.try_dispatch_command("/security", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    line = next(ln for ln in out if "کپچای ورود" in ln)
    assert "🟢" in line


@pytest.mark.asyncio
async def test_security_unknown_and_admin_only(e2e):
    host, d, groups, roles, _ = e2e
    out = await d.try_dispatch_command("/security", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "دسترسی ندارید" in out[0]
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/security nope on", chat_id=CHAT,
                                       user_id=ADMIN, lang="fa")
    assert out and "نامعتبر" in out[0]


# ═══ reportops ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reportops_handle_and_warn(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # یک گزارش ثبت کن (پلاگین report)
    await d.try_dispatch_command("/report 555 تبلیغ مزاحم در گروه", chat_id=CHAT,
                                 user_id=USER1, lang="fa")
    # مدیر فهرست را با دکمه می‌بیند
    out = await d.try_dispatch_command("/handle", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    assert out and "گزارش" in out[0]
    assert d.last_keyboard
    # دکمهٔ هشدار: payload = reportop:<id>:<target>:w
    data_w = d.last_keyboard[0][0]["data"]
    assert data_w.startswith("reportop:") and data_w.endswith(":w")
    row_id = int(data_w.split(":")[1])

    out = await d.dispatch_callback(data_w, chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "هشدار ثبت شد" in out[0]
    # ردیف warn در دفتر + اکشن هشدار در action_sink نیست (فقط ثبت) اما اکشن warn هست
    rows = host.actions.recent(CHAT, limit=100)
    assert any(r["action"] == "warn" and "reportop" in (r["reason"] or "")
               for r in rows)
    # کلیک دوباره → قبلاً رسیدگی شده
    out = await d.dispatch_callback(data_w, chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "قبلاً رسیدگی" in out[0]
    assert row_id > 0


@pytest.mark.asyncio
async def test_reportops_ban_and_non_admin(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/report 555 تبلیغ", chat_id=CHAT,
                                 user_id=USER1, lang="fa")
    await d.try_dispatch_command("/handle", chat_id=CHAT, user_id=ADMIN, lang="fa")
    data_b = d.last_keyboard[1][0]["data"]  # ردیف دوم، دکمهٔ بن
    assert data_b.endswith(":b")
    # کاربر عادی نمی‌تواند کلیک کند
    out = await d.dispatch_callback(data_b, chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "فقط مدیران" in out[0]
    # مدیر کلیک می‌کند → اکشن بن + ردیف ban
    out = await d.dispatch_callback(data_b, chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "بن شد" in out[0]
    assert any(a[1].get("type") == "ban" for a in actions)
    rows = host.actions.recent(CHAT, limit=100)
    assert any(r["action"] == "ban" and "reportop" in (r["reason"] or "") for r in rows)


# ═══ announcer ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_announcer_periodic_send(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/announce 60 | یادآوری: قوانین گروه را رعایت کنید",
                                       chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "اعلان #1" in out[0]
    jobs = host.records["announcer"].module._jobs[CHAT]
    assert 1 in jobs and jobs[1]["interval_s"] == 3600

    # «آخرین ارسال» را به گذشته ببر تا سررسید شود (ماشین تازه‌بوت است)
    jobs[1]["last_sent"] = time.monotonic() - 7200
    await host.tick()
    assert outbox and "قوانین گروه را رعایت کنید" in outbox[-1][1]
    n1 = len(outbox)
    # تیک دوم در همان بازه → ارسالِ دوباره نیست
    await host.tick()
    assert len(outbox) == n1
    # دوباره به گذشته ببر → ارسال بعدی
    jobs[1]["last_sent"] = time.monotonic() - 7200
    await host.tick()
    assert len(outbox) == n1 + 1

    # حذف
    await d.try_dispatch_command("/announcedel 1", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    assert 1 not in host.records["announcer"].module._jobs[CHAT]


# ═══ capsguard ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_capsguard_allcaps_and_run(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/capsguard on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    # جیغ لاتین
    out = await _msg(d, CHAT, USER1, "HELLO EVERYONE STOP SHOUTING NOW")
    assert out and "حروف بزرگ" in out[0]
    assert any(a[1].get("reason") == "caps" for a in actions)
    # تکرار نویسهٔ فارسی
    actions.clear()
    out = await _msg(d, CHAT, USER2, "خخخخخخخخخ این یک تست است")
    assert out and "حروف بزرگ" in out[0]
    # پیام عادی مشکلی ندارد
    actions.clear()
    out = await _msg(d, CHAT, USER2, "سلام، متن عادی و مفید")
    assert not out and not actions
    # خاموش → بی‌اثر
    await d.try_dispatch_command("/capsguard off", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    actions.clear()
    out = await _msg(d, CHAT, USER1, "HELLO EVERYONE SHOUTING AGAIN")
    assert not actions


@pytest.mark.asyncio
async def test_capsguard_staff_exempt(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, 50, "mod", by_user=OWNER)
    await d.try_dispatch_command("/capsguard on", chat_id=CHAT, user_id=ADMIN,
                                 lang="fa")
    await _msg(d, CHAT, 50, "HELLO EVERYONE SHOUTING NOW")
    assert not actions


# ═══ trivia ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_trivia_full_round(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/quiz on", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    assert out and "شروع شد" in out[0]
    assert any("پایتخت فرانسه" in m for m in out)  # سؤال اول
    mod = host.records["trivia"].module
    g = mod._games[CHAT]
    assert g["open"] and g["qno"] == 1

    # پاسخ غلط → باز می‌ماند
    out = await d.try_dispatch_command("/answer 2", chat_id=CHAT, user_id=USER2,
                                       lang="fa", sender_name="مریم")
    assert out and "نادرست" in out[0]
    assert g["open"]
    # پاسخ درست توسط کاربر دیگر → امتیاز
    out = await d.try_dispatch_command("/answer 1", chat_id=CHAT, user_id=USER1,
                                       lang="fa", sender_name="علی")
    assert out and "آفرین" in out[0]
    assert not g["open"] and g["scores"].get(USER1) == 1
    # جدول امتیاز نام را دارد
    out = await d.try_dispatch_command("/score", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "علی" in out[0] and "1" in out[0]

    # تیک → سؤال بعدی (qi پیشروی به سؤال «زبان برنامه‌نویسی»)
    g["next_at"] = 0.0
    await host.tick()
    assert outbox and any("زبان برنامه‌نویسی" in t for _, t in outbox)
    assert g["open"] and g["qno"] == 2


@pytest.mark.asyncio
async def test_trivia_timeout_reveals_and_stops(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/quiz on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    mod = host.records["trivia"].module
    g = mod._games[CHAT]
    g["deadline"] = 0.0  # مهلت تمام شد
    await host.tick()
    assert outbox and "پاسخ درست" in outbox[-1][1]
    assert not g["open"]
    # خاموش‌کردن
    out = await d.try_dispatch_command("/quiz off", chat_id=CHAT, user_id=ADMIN,
                                       lang="fa")
    assert out and "متوقف" in out[0]
    assert CHAT not in mod._games


# ═══ reminder ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reminder_delivery_and_management(e2e):
    host, d, groups, roles, _ = e2e
    _, _, outbox = _wire(host, d)
    out = await d.try_dispatch_command("/remind 5 سلام جلسه فردا", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "یادآوری #1" in out[0]
    mod = host.records["reminder"].module
    assert USER1 in mod._reminders and 1 in mod._reminders[USER1]
    # سررسید فوری → تیک ارسال می‌کند (به چت خصوصی کاربر)
    mod._reminders[USER1][1]["due"] = 0.0
    await host.tick()
    assert outbox and outbox[-1][0] == USER1 and "سلام جلسه" in outbox[-1][1]
    assert 1 not in mod._reminders[USER1]

    # افزودن دو یادآوری و مدیریت
    await d.try_dispatch_command("/remind 10 یادآوری دوم", chat_id=CHAT,
                                 user_id=USER1, lang="fa")
    await d.try_dispatch_command("/remind 20 یادآوری سوم", chat_id=CHAT,
                                 user_id=USER1, lang="fa")
    out = await d.try_dispatch_command("/reminders", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert out and "یادآوری دوم" in out[0]
    await d.try_dispatch_command("/rmremind 2", chat_id=CHAT, user_id=USER1,
                                 lang="fa")
    out = await d.try_dispatch_command("/reminders", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    assert "یادآوری دوم" not in out[0]


# ═══ status ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_status_dashboard(e2e):
    host, d, groups, roles, _ = e2e
    _ = _wire(host, d)
    out = await d.try_dispatch_command("/status", chat_id=CHAT, user_id=USER1,
                                       lang="fa")
    joined = "\n".join(out or [])
    assert "زمان روشن بودن" in joined
    assert "پلاگین" in joined
    assert "captcha" in joined or "antiflood" in joined  # فهرست پلاگین‌ها
