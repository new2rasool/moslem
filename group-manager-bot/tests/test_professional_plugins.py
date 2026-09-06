"""تست‌های حرفه‌ای پلاگین‌های جدید (locks / wordguard / audit / roles_admin).

سناریوهای واقعی بدون تلگرام؛ اجرای «اکشن‌های ساختاریافته» از طریق action_sink و
خطوط لاگ از طریق audit_sink رهگیری می‌شود.
"""

from __future__ import annotations

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
MOD = 11
USER = 99


def _collect_sinks(host, d):
    """اتصال sinkها و برگرداندن جمع‌کننده‌ها."""
    actions: list[tuple] = []
    audit: list[tuple] = []

    def on_action(chat_id, action):
        actions.append((chat_id, action))

    def on_audit(chat_id, lines):
        audit.append((chat_id, list(lines)))

    host.audit_sink = on_audit
    d.action_sink = on_action
    return actions, audit


@pytest.fixture()
def pro(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, MOD, "mod", by_user=OWNER)
    return host, d, groups, roles


async def _msg(d, user_id=USER, text="", ctype="text", fwd=False, **kw):
    return await d.dispatch_event(
        "message", chat_id=CHAT, lang="fa", user_id=user_id, user_name=f"u{user_id}",
        data={"content_type": ctype, "text": text, "caption": "", "is_forward": fwd, **kw},
    )


# ═══ locks: اعمال قفل‌ها و اکشن‌های ساختاریافته ═════════════════════
@pytest.mark.asyncio
async def test_lock_url_deletes_message(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock url", chat_id=CHAT, user_id=ADMIN, lang="fa")

    out = await _msg(d, text="check https://spam.example.com now")
    assert out == []  # حذف بی‌صدا → بدون پیام
    assert actions and actions[-1][1]["type"] == "delete_message"
    assert actions[-1][1]["reason"] == "lock:url"


@pytest.mark.asyncio
async def test_lock_url_warn_mode_replies(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock url warn", chat_id=CHAT, user_id=ADMIN, lang="fa")

    out = await _msg(d, text="go to www.spam.io")
    assert out and "ممنوع" in out[0]
    assert actions[-1][1]["reason"] == "lock:url"


@pytest.mark.asyncio
async def test_lock_forward(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock forward", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await _msg(d, text="پست جالب", fwd=True)
    assert out == []
    assert actions[-1][1]["reason"] == "lock:forward"


@pytest.mark.asyncio
async def test_lock_media_and_admins_exempt(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock photos", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, user_id=USER, ctype="photo")
    assert actions and actions[-1][1]["reason"] == "lock:photos"
    before = len(actions)
    # ادمین معاف است
    await _msg(d, user_id=ADMIN, ctype="photo")
    assert len(actions) == before


@pytest.mark.asyncio
async def test_lock_whitelist_allows_domain(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock url", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/lockaddwl github.com", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, text="https://github.com/ok")
    assert not actions  # هیچ حذفی رخ نداد


@pytest.mark.asyncio
async def test_unlock_stops_enforcement(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/lock url", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/unlock url", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _msg(d, text="https://spam.io")
    assert not actions


# ═══ wordguard: فیلتر کلمات سیاه ════════════════════════════════════
@pytest.mark.asyncio
async def test_blacklist_deletes_and_normalizes(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    # افزودن کلمه با املای عادی؛ پیام با املای کشیده/عربی می‌آید
    await d.try_dispatch_command("/addblacklist تخفیف ویژه", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await _msg(d, text="تخــفیف ویزه بخرید!")
    assert out == []
    assert actions[-1][1]["reason"].startswith("blacklist:")
    # نرمال‌سازی «ویژه→ویزه»؟ نه؛ کلمهٔ «تخفیف ویژه» با فاصلهٔ کشیده سنجیده شد
    assert "تخفیف" in actions[-1][1]["reason"]


@pytest.mark.asyncio
async def test_blacklist_warn_mode(pro):
    host, d, _, _ = pro
    actions, _ = _collect_sinks(host, d)
    await d.try_dispatch_command("/addblacklist اسپم", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/blacklistmode warn", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await _msg(d, text="این یک اسپم تبلیغاتی است")
    assert out and "ممنوع" in out[0]
    assert actions[-1][1]["reason"].startswith("blacklist:")


@pytest.mark.asyncio
async def test_blacklist_list_and_remove(pro):
    host, d, _, _ = pro
    await d.try_dispatch_command("/addblacklist الف ب", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/blacklists", chat_id=CHAT, user_id=USER, lang="fa")
    assert out and "الف" in out[0]
    await d.try_dispatch_command("/rmblacklist الف", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/blacklists", chat_id=CHAT, user_id=USER, lang="fa")
    assert "الف" not in out[0]


# ═══ audit: لاگ خودکار اکشن‌ها ══════════════════════════════════════
@pytest.mark.asyncio
async def test_audit_sink_receives_formatted_log(pro):
    host, d, _, _ = pro
    actions, audit = _collect_sinks(host, d)
    await d.try_dispatch_command(
        "/ban تبلیغ", chat_id=CHAT, user_id=ADMIN, lang="fa",
        reply_to_user_id=555, reply_to_user_name="اسپمر",
    )
    assert audit  # خط لاگ به سینک رسید
    chat_id, lines = audit[-1]
    assert chat_id == CHAT and lines
    text = lines[0]
    assert "بن" in text and "555" in text and "تبلیغ" in text  # برچسب/هدف/دلیل


@pytest.mark.asyncio
async def test_audit_log_command_shows_history(pro):
    host, d, _, _ = pro
    _collect_sinks(host, d)
    await d.try_dispatch_command(
        "/kick مزاحم", chat_id=CHAT, user_id=MOD, lang="fa", reply_to_user_id=666
    )
    out = await d.try_dispatch_command("/log", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "اخراج" in out[0] and "666" in out[0]


@pytest.mark.asyncio
async def test_setlog_persists(pro):
    host, d, groups, _ = pro
    out = await d.try_dispatch_command("/setlog @log_ch", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "@log_ch" in out[0]
    assert groups.get(CHAT).settings.get("log_channel") == "@log_ch"


# ═══ roles_admin: ارتقا/عزل حرفه‌ای ═════════════════════════════════
@pytest.mark.asyncio
async def test_promote_and_demote_by_admin(pro):
    host, d, _, roles = pro
    actions, audit = _collect_sinks(host, d)
    out = await d.try_dispatch_command("/promote mod 55", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "مدیر میانی" in out[0] or out and "ارتقا" in out[0]
    assert roles.get_role(CHAT, 55) == "mod"
    # در دفتر حسابرسی ثبت شد
    kinds = [a["action"] for a in host.actions.recent(CHAT, limit=5)]
    assert "promote" in kinds

    out = await d.try_dispatch_command("/demote 55", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert roles.get_role(CHAT, 55) is None


@pytest.mark.asyncio
async def test_promote_hierarchy_denied(pro):
    host, d, _, roles = pro
    # MOD اصلاً به فرمان promote دسترسی ندارد (نیاز ADMIN+)
    out = await d.try_dispatch_command("/promote admin 55", chat_id=CHAT, user_id=MOD, lang="fa")
    assert out and "دسترسی ندارید" in out[0]
    assert roles.get_role(CHAT, 55) is None


@pytest.mark.asyncio
async def test_co_owner_promotion_requires_higher(pro):
    host, d, _, roles = pro
    # ADMIN نمی‌تواند co_owner بسازد (نیاز به CO_OWNER+)
    out = await d.try_dispatch_command("/promote co_owner 55", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "کافی نیست" in out[0]
    # مالک ربات می‌تواند
    out = await d.try_dispatch_command("/promote co_owner 55", chat_id=CHAT, user_id=OWNER, lang="fa")
    assert roles.get_role(CHAT, 55) == "co_owner"


@pytest.mark.asyncio
async def test_cannot_demote_same_level(pro):
    host, d, _, roles = pro
    roles.set_role(CHAT, 77, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/demote 77", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "بالاتر" in out[0]  # ادمین نمی‌تواند ادمینِ دیگر را عزل کند
    assert roles.get_role(CHAT, 77) == "admin"  # دست‌نخورده ماند


@pytest.mark.asyncio
async def test_adminlist(pro):
    host, d, _, roles = pro
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    roles.set_role(CHAT, MOD, "mod", by_user=OWNER)
    out = await d.try_dispatch_command("/adminlist", chat_id=CHAT, user_id=USER, lang="fa")
    assert out and "ادمین ربات" in out[0] and "مدیر میانی" in out[0]
