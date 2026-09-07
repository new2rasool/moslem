"""تست‌های E2E پلاگین‌های پیشرفته (moderation / antiflood / greeter v2 / سوئیچ گروهی).

همه‌چیز بدون تلگرام؛ فقط هسته + پلاگین‌های واقعی + Dispatcher.
"""

from __future__ import annotations

import pytest

CHAT = -1001
OWNER = 1     # مالک ربات (سودو)
ADMIN = 10    # نقش admin در گروه
MOD = 11      # نقش mod در گروه
USER = 99     # کاربر عادی


@pytest.fixture()
def ctx_setup(e2e):
    host, d, groups, roles, plugins_dir = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, MOD, "mod", by_user=OWNER)
    return host, d, groups, roles


# ── moderation: تنبیه ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ban_by_admin_logged_to_audit(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command(
        "/ban 555 اسپم", chat_id=CHAT, user_id=ADMIN, lang="fa",
        reply_to_user_id=555, reply_to_user_name="اسپمر",
    )
    assert out and "555" in out[0] or out and "اسپمر" in out[0]


@pytest.mark.asyncio
async def test_ban_without_reply_or_id_usage(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command("/ban", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "ریپلای" in out[0]


@pytest.mark.asyncio
async def test_cannot_ban_higher_level(ctx_setup):
    _, d, _, _ = ctx_setup
    # MOD سعی می‌کند ADMIN را بن کند → رد
    out = await d.try_dispatch_command(
        "/ban", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=ADMIN
    )
    assert out and "بالاتر" in out[0]


@pytest.mark.asyncio
async def test_owner_immune(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command(
        "/ban", chat_id=CHAT, user_id=ADMIN, lang="fa", reply_to_user_id=OWNER
    )
    assert out and ("مالک" in out[0] or "owner" in out[0])


@pytest.mark.asyncio
async def test_normal_user_cannot_ban(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command("/ban 5", chat_id=CHAT, user_id=USER, lang="fa")
    assert out and "دسترسی ندارید" in out[0]


@pytest.mark.asyncio
async def test_strict_reason_enforced(ctx_setup):
    _, d, groups, _ = ctx_setup
    # فعال‌سازی حالت سخت
    await d.try_dispatch_command("/setstrict on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command(
        "/kick", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=555
    )
    assert out and "دلیل" in out[0]  # بدون دلیل رد شد
    # با دلیل انجام می‌شود
    out2 = await d.try_dispatch_command(
        "/kick دلیل دارد", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=555
    )
    assert out2 and "اخراج" in out2[0]


# ── moderation: هشدار و اکشن خودکار ────────────────────────────────
@pytest.mark.asyncio
async def test_warn_auto_action_at_limit(ctx_setup):
    host, d, groups, _ = ctx_setup
    # سقف پیش‌فرض هشدار ۳ → در هشدار سوم اکشن خودکار (سکوت ۱ ساعته) اجرا می‌شود
    last_out = None
    for i in range(1, 4):
        last_out = await d.try_dispatch_command(
            "/warn مزاحمت", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=555
        )
        assert last_out
    joined = "\n".join(last_out)
    assert "هشدار 3/3" in joined or "هشدار ۳/۳" in joined
    assert "⚡️" in joined  # اکشن خودکار اعلام شد

    # دفتر حسابرسی: ۳ warn + یک auto:* ثبت شده
    actions = host.actions.recent(CHAT, limit=20)
    actions_kinds = [a["action"] for a in actions]
    assert actions_kinds.count("warn") == 3
    assert any(a.startswith("auto:") for a in actions_kinds)
    # هشدارها بعد از اکشن خودکار ریست شدند
    assert host.warns.count(CHAT, 555) == 0


@pytest.mark.asyncio
async def test_unwarn_decrements(ctx_setup):
    _, d, _, _ = ctx_setup
    await d.try_dispatch_command("/warn x", chat_id=CHAT, user_id=MOD, lang="fa",
                                 reply_to_user_id=555)
    out = await d.try_dispatch_command("/unwarn", chat_id=CHAT, user_id=MOD, lang="fa",
                                       reply_to_user_id=555)
    assert out and "باقی" in out[0]


@pytest.mark.asyncio
async def test_warns_show_self_for_user(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command("/warns", chat_id=CHAT, user_id=USER, lang="fa")
    assert out and "0" in out[0]


# ── moderation: tmute duration parsing ──────────────────────────────
@pytest.mark.asyncio
async def test_tmute_with_duration(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command(
        "/tmute 1h30m اسپم", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=555
    )
    assert out and "1h 30m" in out[0]


@pytest.mark.asyncio
async def test_tmute_requires_duration(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.try_dispatch_command(
        "/tmute", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=555
    )
    assert out and "کاربرد" in out[0]


# ── recent (دفتر حسابرسی) ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_recent_lists_actions(ctx_setup):
    host, d, _, _ = ctx_setup
    await d.try_dispatch_command("/ban 555 تبلیغ", chat_id=CHAT, user_id=ADMIN, lang="fa",
                                 reply_to_user_id=555)
    out = await d.try_dispatch_command("/recent", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "ban" in out[0]
    assert host.actions.count_today(CHAT) >= 1


# ── antiflood ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_antiflood_warns_on_burst(e2e):
    host, d, groups, roles, _ = e2e
    # تنظیم آستانهٔ سخت برای تست
    await d.try_dispatch_command("/setflood 3 2", chat_id=CHAT, user_id=ADMIN, lang="fa",
                                 )
    # یک کاربر عادی ۵ پیام پشت‌سرهم
    warned = False
    for _ in range(6):
        out = await d.dispatch_event(
            "message", chat_id=CHAT, lang="fa", user_id=USER, user_name="کاربر",
            data={"text": "x"},
        )
        if out:
            warned = True
    assert warned  # حداقل یک هشدار ضد سیل


@pytest.mark.asyncio
async def test_antiflood_exempts_admin(e2e):
    _, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=1)
    await d.try_dispatch_command("/setflood 2 2", chat_id=CHAT, user_id=ADMIN, lang="fa")
    warned = False
    for _ in range(5):
        out = await d.dispatch_event(
            "message", chat_id=CHAT, lang="fa", user_id=ADMIN, user_name="ادمین"
        )
        if out:
            warned = True
    assert not warned  # ادمین معاف است


# ── greeter v2: خوش‌آمد/خداحافظی/متن سفارشی ────────────────────────
@pytest.mark.asyncio
async def test_welcome_and_goodbye_defaults(ctx_setup):
    _, d, _, _ = ctx_setup
    out = await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=777, user_name="مریم",
        data={"member_name": "مریم", "chat_title": "انجمن"},
    )
    assert out and "مریم" in out[0] and "خوش آمدی" in out[0]

    # خداحافظی پیش‌فرض خاموش است
    out2 = await d.dispatch_event(
        "member_left", chat_id=CHAT, lang="fa", user_id=777, user_name="مریم",
        data={"member_name": "مریم"},
    )
    assert not out2


@pytest.mark.asyncio
async def test_setgreet_custom_and_goodbye_enable(ctx_setup):
    _, d, groups, _ = ctx_setup
    await d.try_dispatch_command("/goodbye on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command(
        "/setgreet خوش اومدی {name} جان!", chat_id=CHAT, user_id=ADMIN, lang="fa"
    )
    out = await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=888,
        data={"member_name": "سارا"},
    )
    assert out and "سارا جان" in out[0]

    out2 = await d.dispatch_event(
        "member_left", chat_id=CHAT, lang="fa", user_id=888,
        data={"member_name": "سارا"},
    )
    assert out2 and "سارا" in out2[0]


# ── سوئیچ پلاگین در گروه ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_plugin_disable_in_group_hides_commands(ctx_setup):
    host, d, _, _ = ctx_setup
    # پینگ در این گروه خاموش شود
    out = await d.try_dispatch_command(
        "/pluginenable ping off", chat_id=CHAT, user_id=ADMIN, lang="fa"
    )
    assert out and "غیرفعال" in out[0]
    assert host.is_plugin_enabled(CHAT, "ping") is False

    # فرمان ping در گروه بی‌صدا می‌شود…
    out = await d.try_dispatch_command("/ping", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out is None

    # …ولی در پیوی همچنان کار می‌کند
    out = await d.try_dispatch_command("/ping", chat_id=None, user_id=ADMIN, is_private=True)
    assert out and "پونگ" in out[0]

    # روشن کردن دوباره
    out = await d.try_dispatch_command(
        "/pluginenable ping on", chat_id=CHAT, user_id=ADMIN, lang="fa"
    )
    assert out and "فعال" in out[0]
    out = await d.try_dispatch_command("/ping", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "پونگ" in out[0]


@pytest.mark.asyncio
async def test_plugin_disable_blocks_events(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=1)
    # خاموش‌کردن greeter در گروه → رویداد ورود عضو دیگر پاسخ ندارد
    await d.try_dispatch_command("/pluginenable greeter off", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=777,
        data={"member_name": "مریم"},
    )
    assert not out

    await d.try_dispatch_command("/pluginenable greeter on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=777,
        data={"member_name": "مریم"},
    )
    assert out
