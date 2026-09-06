"""تست‌های پلاگین‌های نسل ششم (۷ پلاگین): joinapprove، rules، antirepeat،
slowmode، lookup، newcomer_guard، globalguard."""

from __future__ import annotations

import pytest

CHAT = -1001
OWNER = 1
SUDO = 2
ADMIN = 10
USER1 = 100
USER2 = 101
NEW = 777

LONG = "این یک متن بلند تکراری برای سنجش ضدکپی‌پیست است که به اندازهٔ کافی طول دارد " * 2


def _wire(host, d):
    actions: list[tuple] = []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    d.action_sink = host.action_sink
    return actions


def _msg(d, chat_id, user_id, text, user_name="کاربر"):
    return d.dispatch_event(
        "message", chat_id=chat_id, lang="fa", user_id=user_id, user_name=user_name,
        data={"text": text, "content_type": "text", "sender_name": user_name},
    )


def _join(d, user_id, name="تازه"):
    return d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=user_id, user_name=name,
        data={"member_id": user_id, "member_name": name},
    )


# ═══ joinapprove ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_joinapprove_full_flow(e2e):
    host, d, groups, roles, _ = e2e
    actions, audit = [], []
    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    d.action_sink = host.action_sink
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/joinapprove on", chat_id=CHAT, user_id=ADMIN, lang="fa")

    out = await _join(d, NEW)
    assert any("درخواست ورود" in m for m in out)
    assert d.last_keyboard
    data_a = d.last_keyboard[0][0]["data"]
    data_r = d.last_keyboard[0][1]["data"]
    assert data_a.startswith("ja:a:") and data_r.startswith("ja:r:")
    # ورود → محدودسازی
    assert any(a[1].get("type") == "restrict" for a in actions)

    # غیرمدیر نمی‌تواند تأیید کند
    out = await d.dispatch_callback(data_a, chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "فقط مدیران" in out[0]
    # تأیید توسط مدیر
    actions.clear()
    out = await d.dispatch_callback(data_a, chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "تأیید شد" in out[0]
    assert any(a[1].get("type") == "unrestrict" for a in actions)
    assert any("join_approve" in ln for _, lines in audit for ln in lines)

    # رد: کاربر دیگر
    out = await _join(d, 778)
    data_r2 = d.last_keyboard[0][1]["data"]
    out = await d.dispatch_callback(data_r2, chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "رد شد" in out[0]


@pytest.mark.asyncio
async def test_joinapprove_timeout_kicks(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/joinapprove on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _join(d, NEW)
    mod = host.records["joinapprove"].module
    key = (CHAT, NEW)
    assert key in mod._pending
    mod._pending[key]["deadline"] = 0  # منقضی
    await host.tick()
    assert any(a[1].get("type") == "kick" and a[1].get("reason") == "joinapprove:timeout"
               for a in actions)
    assert key not in mod._pending


# ═══ rules ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_rules_set_list_and_auto_send(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command(
        "/setrules احترام متقابل | اسپم ممنوع", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "قوانین ذخیره شد" in out[0]
    out = await d.try_dispatch_command("/rules", chat_id=CHAT, user_id=USER1, lang="fa")
    joined = "\n".join(out)
    assert "1. احترام متقابل" in joined and "2. اسپم ممنوع" in joined
    # ارسال خودکار به تازه‌وارد
    out = await _join(d, NEW, "تازه وارد")
    assert any("قوانین" in m and "احترام متقابل" in m for m in out)
    # حذف
    await d.try_dispatch_command("/delrules", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/rules", chat_id=CHAT, user_id=USER1, lang="fa")
    assert "تنظیم نشده" in out[0]


# ═══ antirepeat ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_antirepeat_deletes_duplicate(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    await _msg(d, CHAT, USER1, LONG)
    out = await _msg(d, CHAT, USER1, LONG)
    assert out and "تکراری" in out[0]
    assert any(a[1].get("type") == "delete_message" and a[1].get("reason") == "repeat"
               for a in actions)
    # پیام متفاوت مشکلی ندارد
    actions.clear()
    out = await _msg(d, CHAT, USER1, "یک پیام کاملاً متفاوت و جدید برای بررسی رفتار صحیح")
    assert not out and not actions


@pytest.mark.asyncio
async def test_antirepeat_toggle_off(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/antirepeat off", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, CHAT, USER1, LONG)
    out = await _msg(d, CHAT, USER1, LONG)
    assert not out and not actions


# ═══ slowmode ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_slowmode_deletes_early_message(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/slowmode on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/setslowmode 3600", chat_id=CHAT, user_id=ADMIN, lang="fa")
    mod = host.records["slowmode"].module
    fake = {"t": 1000.0}
    mod._now = lambda: fake["t"]
    await _msg(d, CHAT, USER1, "اول")
    actions.clear()
    fake["t"] += 10  # هنوز زود است (فاصلهٔ ۳۶۰۰)
    out = await _msg(d, CHAT, USER1, "دوم")
    assert out and "آرام" in out[0]
    assert any(a[1].get("reason") == "slowmode" for a in actions)
    # پس از گذشت فاصله → مجاز
    actions.clear()
    fake["t"] += 4000
    out = await _msg(d, CHAT, USER1, "سوم")
    assert not out and not actions


@pytest.mark.asyncio
async def test_slowmode_staff_exempt(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, 50, "mod", by_user=OWNER)
    await d.try_dispatch_command("/slowmode on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/setslowmode 3600", chat_id=CHAT, user_id=ADMIN, lang="fa")
    mod = host.records["slowmode"].module
    mod._now = lambda: 5.0
    await _msg(d, CHAT, 50, "پیام مدیر")
    actions.clear()
    await _msg(d, CHAT, 50, "پیام مدیر دوم")
    assert not actions


# ═══ lookup ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lookup_card_self(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # سابقه بسازیم
    await d.try_dispatch_command("/warn 555 اسپم", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/lookup 555", chat_id=CHAT, user_id=ADMIN, lang="fa")
    joined = "\n".join(out)
    assert "555" in joined and "اخطارها: 1" in joined and "اسپم" in joined
    assert "تاریخچه" not in joined  # فقط warn ثبت شده (جزو punish نیست؟ در ادامه)


@pytest.mark.asyncio
async def test_lookup_self_no_arg_and_role_label(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, MOD_ROLE := 55, "mod", by_user=OWNER)
    out = await d.try_dispatch_command("/lookup", chat_id=CHAT, user_id=55, lang="fa")
    joined = "\n".join(out)
    assert "مدیر میانی" in joined and "55" in joined


# ═══ newcomer_guard ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_newcomer_guard_blocks_until_period(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/newcomer on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/newcomermin 10", chat_id=CHAT, user_id=ADMIN, lang="fa")
    mod = host.records["newcomer_guard"].module
    fake = {"t": 5000.0}
    mod._now = lambda: fake["t"]
    await _join(d, NEW)
    out = await _msg(d, CHAT, NEW, "سلام من تازه آمدم")
    assert out and "صبر کنید" in out[0]
    assert any(a[1].get("reason") == "newcomer_guard" for a in actions)
    # پس از پایان مهلت
    actions.clear()
    fake["t"] += 60 * 11
    out = await _msg(d, CHAT, NEW, "الان می‌توانم؟")
    assert not out and not actions


# ═══ globalguard ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_globalguard_cross_group_delete(e2e):
    host, d, groups, roles, _ = e2e
    actions = _wire(host, d)
    out = await d.try_dispatch_command("/ggadd تبلیغات", chat_id=CHAT, user_id=SUDO, lang="fa")
    assert out and "اضافه شد" in out[0]
    # در دو گروه مختلف اثر دارد
    out = await _msg(d, CHAT, USER1, "این پیام تبلیغات دارد")
    assert out and "ممنوع" in out[0]
    assert any(a[1].get("reason", "").startswith("gg:") for a in actions)
    actions.clear()
    out = await _msg(d, CHAT + 1, USER2, "اینجا هم تبلیغات هست")
    assert any(a[1].get("reason", "").startswith("gg:") for a in actions)
    # حذف از فهرست
    out = await d.try_dispatch_command("/ggdel تبلیغات", chat_id=CHAT, user_id=SUDO, lang="fa")
    assert out and "حذف شد" in out[0]
    actions.clear()
    await _msg(d, CHAT, USER1, "این پیام تبلیغات دارد دوباره")
    assert not actions


@pytest.mark.asyncio
async def test_globalguard_sudo_only(e2e):
    host, d, groups, roles, _ = e2e
    out = await d.try_dispatch_command("/ggadd کلمه", chat_id=CHAT, user_id=USER1, lang="fa")
    assert out and "دسترسی ندارید" in out[0]
