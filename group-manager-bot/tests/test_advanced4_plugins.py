"""تست‌های پلاگین‌های بسیار پیشرفته: automod (تشدید خودکار)، report، gban."""

from __future__ import annotations

import pytest

CHAT = -1001
OWNER = 1
SUDO = 2            # سودو (sudo_ids=(2,))
ADMIN = 10
USER1 = 100
SPAM1 = 555
SPAM2 = 556
GLOB = 9999


def _wire(host, d):
    actions: list[tuple] = []
    audit: list[tuple] = []
    outbox: list[tuple] = []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    host.out_sink = lambda chat, text: outbox.append((chat, text))
    d.action_sink = host.action_sink
    return actions, audit, outbox


def _join(d, user_id, name="تازه"):
    return d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=user_id, user_name=name,
        data={"member_id": user_id, "member_name": name},
    )


# ═══ automod ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_automod_off_by_default(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/kick 555", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/kick 555", chat_id=CHAT, user_id=ADMIN, lang="fa")
    # هیچ بن خودکاری (خاموش پیش‌فرض)
    assert not [a for a in actions if a[1].get("type") == "ban"]


@pytest.mark.asyncio
async def test_automod_repeat_kick_bans(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/automod on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "روشن" in out[0]

    await d.try_dispatch_command("/kick 555", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/kick 555", chat_id=CHAT, user_id=ADMIN, lang="fa")

    bans = [a for a in actions if a[1].get("type") == "ban"]
    assert bans and bans[0][1]["reason"].startswith("automod:")
    # اطلاع‌رسانی در گروه
    assert outbox and "بن شد" in outbox[-1][1]
    # ثبت در دفتر حسابرسی → خط لاگ خودکار: بن
    assert any("خودکار: بن" in ln for _, lines in audit for ln in lines)

    # اخراج سوم → دیگر تشدید نمی‌شود (ردیف بن موجود = توقف)
    await d.try_dispatch_command("/kick 555", chat_id=CHAT, user_id=ADMIN, lang="fa")
    bans2 = [a for a in actions if a[1].get("type") == "ban"]
    assert len(bans2) == 1


@pytest.mark.asyncio
async def test_automod_repeated_mutes_ban(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/automod on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    for _ in range(3):
        await d.try_dispatch_command("/mute 556", chat_id=CHAT, user_id=ADMIN, lang="fa")
    bans = [a for a in actions if a[1].get("type") == "ban"]
    assert bans and bans[0][1]["user_id"] == 556


@pytest.mark.asyncio
async def test_automod_staff_protected(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, 77, "mod", by_user=OWNER)  # هدف، کارکن است
    await d.try_dispatch_command("/automod on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    # تزریق مستقیم دو اخراج برای کارکن (بدون درگیری با سلسله‌مراتب فرمان‌ها)
    api = host.records["ping"].api
    for _ in range(2):
        await api.record_action(CHAT, "kick", 77, ADMIN, reason="تست")
    assert not [a for a in actions if a[1].get("type") == "ban"]


@pytest.mark.asyncio
async def test_automod_ignores_bot_rows(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/automod on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    api = host.records["ping"].api
    # ردیف‌های توسطِ خود ربات (by_user=0) → بدون واکنش
    for _ in range(3):
        await api.record_action(CHAT, "kick", 600, 0, reason="خودکار")
    assert not [a for a in actions if a[1].get("type") == "ban"]


# ═══ report ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_report_records_and_notifies(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, outbox = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command(
        "/report 555 تبلیغ مزاحم در گروه", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "گزارش شما" in out[0]
    # خط لاگ گزارش + اطلاع‌رسانی
    assert any("📮" in ln for _, lines in audit for ln in lines)
    assert any("تبلیغ مزاحم" in ln for _, lines in audit for ln in lines)
    assert outbox and "گزارش" in outbox[-1][1]
    # در دفتر حسابرسی ثبت شد
    rows = host.records["ping"].api.actions.recent(CHAT, limit=10)
    reports = [r for r in rows if r["action"] == "report"]
    assert len(reports) == 1 and reports[0]["reason"] == "تبلیغ مزاحم در گروه"


@pytest.mark.asyncio
async def test_report_cooldown(e2e):
    host, d, groups, roles, _ = e2e
    await d.try_dispatch_command("/report 555 اول", chat_id=CHAT, user_id=USER1, lang="fa")
    out = await d.try_dispatch_command("/report 556 دوم", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "صبر کنید" in out[0]


@pytest.mark.asyncio
async def test_report_hourly_limit(e2e):
    host, d, groups, roles, _ = e2e
    import time as _t
    host.cache.set(f"report:hr:{CHAT}:{USER1}", [_t.monotonic()] * 3, ttl_s=3600)
    out = await d.try_dispatch_command("/report 555 دلیل آزمایشی", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "سقف" in out[0]


@pytest.mark.asyncio
async def test_report_cannot_report_staff_or_self(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/report 10 هدف ادمین", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "مدیران" in out[0]
    out = await d.try_dispatch_command("/report 100 خودم", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "خودتان" in out[0]


@pytest.mark.asyncio
async def test_reports_list_by_admin(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/report 555 تبلیغ مزاحم", chat_id=CHAT,
                                 user_id=USER1, lang="fa")
    out = await d.try_dispatch_command("/reports", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "555" in out[0] and "تبلیغ مزاحم" in out[0]


# ═══ gban ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_gban_blocks_join(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit, _ = _wire(host, d)
    out = await d.try_dispatch_command("/gban 9999 اسپمر سراسری", chat_id=CHAT,
                                       user_id=SUDO, lang="fa")
    assert out and "بن سراسری اضافه شد" in out[0]
    out = await d.try_dispatch_command("/gbanlist", chat_id=CHAT, user_id=SUDO, lang="fa")
    assert out and "9999" in out[0]

    out = await _join(d, GLOB)
    joined = "\n".join(out)
    assert "بن سراسری" in joined
    bans = [a for a in actions if a[1].get("type") == "ban"]
    assert bans and bans[0][1]["reason"].startswith("gban:")


@pytest.mark.asyncio
async def test_ungban_allows_join(e2e):
    host, d, groups, roles, _ = e2e
    actions, *_ = _wire(host, d)
    await d.try_dispatch_command("/gban 9999 اسپمر", chat_id=CHAT, user_id=SUDO, lang="fa")
    await d.try_dispatch_command("/ungban 9999", chat_id=CHAT, user_id=SUDO, lang="fa")
    await _join(d, GLOB)
    assert not [a for a in actions if a[1].get("type") == "ban"]


@pytest.mark.asyncio
async def test_gban_sudo_only(e2e):
    host, d, groups, roles, _ = e2e
    out = await d.try_dispatch_command("/gban 9999 اسپمر", chat_id=CHAT,
                                       user_id=USER1, lang="fa")
    assert out and "دسترسی ندارید" in out[0]
