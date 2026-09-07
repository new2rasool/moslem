"""تست‌های پلاگین‌های کاملاً پیشرفته: captcha، antiraid، filters + زیرساخت tick/keyboard."""

from __future__ import annotations

import time

import pytest

CHAT = -1001
OWNER = 1
ADMIN = 10
NEW = 777          # کاربر تازهوارد
SPAMMER = 999


def _collect(host, d):
    actions: list[tuple] = []
    audit: list[tuple] = []
    outbox: list[tuple] = []

    host.action_sink = lambda chat, a: actions.append((chat, a))
    host.audit_sink = lambda chat, lines: audit.append((chat, lines))
    host.out_sink = lambda chat, text: outbox.append((chat, text))
    d.action_sink = host.action_sink
    return actions, audit, outbox


async def _join(d, user_id, name="عضو"):
    return await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=user_id, user_name=name,
        data={"member_id": user_id, "member_name": name, "chat_title": "انجمن"},
    )


# ═══ زیرساخت: صفحه‌کلید + تیک ───────────────────────────────────────
@pytest.mark.asyncio
async def test_host_tick_runs(e2e):
    host, d, *_ = e2e
    await host.tick()  # نباید خطا بدهد (on_tick پلاگین‌ها)
    # حلقهٔ پس‌زمینه شروع/توقف امن
    await host.start_background(interval_s=0.05)
    await host.stop_background()


# ═══ captcha: جریان کامل دکمه‌ها ────────────────────────────────────
@pytest.mark.asyncio
async def test_captcha_join_sends_buttons_and_restricts(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN, lang="fa")

    out = await _join(d, NEW)
    # پیام پرسش + دکمه‌ها
    assert out and "انسان" in "".join(out) or any("انسان" in m for m in out)
    assert d.last_keyboard  # صفحه‌کلید ساخته شد
    data0 = d.last_keyboard[0][0]["data"]
    assert data0.startswith("captcha:")
    # اکشن محدودسازی ثبت شد
    assert actions and actions[-1][1]["reason"] == "captcha:pending"


@pytest.mark.asyncio
async def test_captcha_correct_answer_unrestricts(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _join(d, NEW)

    state = host.cache.get(f"captcha:{CHAT}:{NEW}")
    assert state is not None and "answer" in state
    answer = state["answer"]
    data = f"captcha:{CHAT}:{NEW}:{answer}"
    out = await d.dispatch_callback(data, chat_id=CHAT, user_id=NEW, lang="fa")
    assert out and "خوش آمدید" in out[0]
    assert actions[-1][1]["reason"] == "captcha:passed"
    assert host.cache.get(f"captcha:{CHAT}:{NEW}") is None


@pytest.mark.asyncio
async def test_captcha_wrong_answers_lead_to_kick(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _join(d, NEW)
    state = host.cache.get(f"captcha:{CHAT}:{NEW}")
    wrong = state["answer"] + 99  # قطعاً غلط

    for attempt in range(1, 4):
        out = await d.dispatch_callback(
            f"captcha:{CHAT}:{NEW}:{wrong}", chat_id=CHAT, user_id=NEW, lang="fa"
        )
    assert out
    # تلاش سوم → اخراج
    assert actions[-1][1]["reason"] == "captcha:failed"
    assert host.cache.get(f"captcha:{CHAT}:{NEW}") is None


@pytest.mark.asyncio
async def test_captcha_expiry_via_tick_kicks(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, outbox = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await _join(d, NEW)

    # انقضای دستی مهلت (شبیه‌سازی گذر زمان)
    mod = host.records["captcha"].module
    key = (CHAT, NEW)
    assert key in mod._pending
    mod._pending[key]["deadline"] = time.monotonic() - 1

    await host.tick()
    assert outbox and "خارج شد" in outbox[-1][1]
    assert actions and actions[-1][1]["reason"] == "captcha:timeout"


@pytest.mark.asyncio
async def test_captcha_off_for_admins(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, _ = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/captcha on", chat_id=CHAT, user_id=ADMIN, lang="fa")

    # ورود یک ادمین → بدون کپچا
    await d.dispatch_event(
        "member_joined", chat_id=CHAT, lang="fa", user_id=ADMIN, user_name="ادمین",
        data={"member_id": ADMIN, "member_name": "ادمین"},
    )
    assert not [a for a in actions if a[1].get("reason") == "captcha:pending"]


# ═══ antiraid: تشخیص موج ورود و قفل ─────────────────────────────────
@pytest.mark.asyncio
async def test_antiraid_detects_burst_and_locks(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, outbox = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/antiraid on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    await d.try_dispatch_command("/raidset 3 30 60", chat_id=CHAT, user_id=ADMIN, lang="fa")

    # ورودهای پشت‌سرهم
    last_out = []
    for i in range(4):
        last_out = await _join(d, 900 + i)
    # پیام هشدار راید باید آمده باشد
    assert any("راید" in m or "موج ورود" in m for m in last_out)
    # اکشن lock_join صادر شد
    assert any(a[1].get("type") == "lock_join" for a in actions)


@pytest.mark.asyncio
async def test_antiraid_manual_lock_and_release(e2e):
    host, d, groups, roles, _ = e2e
    actions, _, outbox = _collect(host, d)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    out = await d.try_dispatch_command("/raid on", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "قفل" in out[0]
    assert any(a[1].get("type") == "lock_join" for a in actions)

    out = await d.try_dispatch_command("/raid off", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "برداشته" in out[0]


# ═══ filters: پاسخ خودکار ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_filter_auto_reply(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command(
        "/addfilter قوانین => قوانین گروه را ببینید: /rules", chat_id=CHAT, user_id=ADMIN, lang="fa"
    )
    out = await d.dispatch_event(
        "message", chat_id=CHAT, lang="fa", user_id=NEW,
        data={"text": "قوانین گروه چیه؟", "content_type": "text"},
    )
    assert out and "قوانین گروه را ببینید" in out[0]


@pytest.mark.asyncio
async def test_filter_admins_exempt(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/addfilter سلام => درود!", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.dispatch_event(
        "message", chat_id=CHAT, lang="fa", user_id=ADMIN,
        data={"text": "سلام", "content_type": "text"},
    )
    assert not out


@pytest.mark.asyncio
async def test_filter_list_and_remove(e2e):
    host, d, groups, roles, _ = e2e
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await d.try_dispatch_command("/addfilter الف => پاسخ الف", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/filters", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert out and "الف" in out[0]
    await d.try_dispatch_command("/rmfilter الف", chat_id=CHAT, user_id=ADMIN, lang="fa")
    out = await d.try_dispatch_command("/filters", chat_id=CHAT, user_id=ADMIN, lang="fa")
    assert "الف" not in out[0]
