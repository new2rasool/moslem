"""تست‌های آداپتور تلگرام (کانکتور) — بدون Pyrogram/اینترنت.

FakeClient پیاده‌سازی‌کنندهٔ پروتکلِ کلاینتِ کانکتور است؛ کل منطق اتصال
(فرمان/رویداد/دکمه/اکشن فیزیکی/کانال لاگ) با آن آزموده می‌شود.
"""

from __future__ import annotations

import pytest

from bot.adapter.connector import TelegramConnector
from bot.adapter.models import (
    IncomingCallback,
    IncomingChat,
    IncomingMessage,
    IncomingUser,
)

CHAT = -1001
OWNER = 1
ADMIN = 10
USER1 = 100
NEW = 777
TARGET = 555
LOG_CHANNEL = -100987


class FakeClient:
    """کلاینت ساختگی — هر تماس را ثبت می‌کند."""

    def __init__(self) -> None:
        self.sends: list[tuple] = []
        self.deleted: list[tuple] = []
        self.restricts: list[tuple] = []
        self.bans: list[tuple] = []
        self.kicks: list[tuple] = []
        self.locks: list[tuple] = []
        self.promotes: list[tuple] = []
        self.demotes: list[tuple] = []
        self.answered: list[str] = []

    async def send_message(self, chat_id, text, *, reply_to=None, buttons=None):
        self.sends.append((chat_id, text, reply_to, buttons))

    async def delete_messages(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))

    async def restrict(self, chat_id, user_id, *, muted, until=None):
        self.restricts.append((chat_id, user_id, muted, until))

    async def ban(self, chat_id, user_id):
        self.bans.append((chat_id, user_id))

    async def kick(self, chat_id, user_id):
        self.kicks.append((chat_id, user_id))

    async def lock_join(self, chat_id, locked):
        self.locks.append((chat_id, locked))

    async def promote(self, chat_id, user_id, role=None):
        self.promotes.append((chat_id, user_id, role))

    async def demote(self, chat_id, user_id):
        self.demotes.append((chat_id, user_id))

    async def answer_callback(self, callback_id, text=""):
        self.answered.append(callback_id)


def _conn(e2e):
    host, d, groups, roles, _ = e2e
    client = FakeClient()
    connector = TelegramConnector(host, d, client, default_lang="fa")
    return host, d, groups, roles, client, connector


def _msg(chat_id=CHAT, text="", user=None, msg_id=1, content_type="text",
         forwarded=False, chat_title="انجمن"):
    if user is None:
        user = IncomingUser(id=USER1, first_name="علی")
    return IncomingMessage(
        id=msg_id,
        chat=IncomingChat(id=chat_id, title=chat_title),
        user=user,
        text=text,
        content_type=content_type,
        forwarded=forwarded,
    )


# ═══ فرمان متنی → پاسخ ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_command_reply_is_sent(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await conn.handle_message(_msg(text="/rules"))
    assert client.sends
    # پاسخ به عنوان پیام تازه به همان گروه
    assert client.sends[0][0] == CHAT and "قوانین" in client.sends[0][1]


# ═══ اکشن فیزیکی حذف (capsguard) ────────────────────────────────────
@pytest.mark.asyncio
async def test_physical_delete_via_event(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await conn.handle_message(_msg(text="/capsguard on", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))
    await conn.handle_message(_msg(text="HELLO EVERYONE STOP SHOUTING NOW",
                                   msg_id=42))
    assert any(cid == CHAT and mid == 42 for cid, mid in client.deleted)
    assert any("حروف بزرگ" in t for _, t, _, _ in client.sends)


# ═══ ورود عضو → کپچا (restrict + دکمه) ─────────────────────────────
@pytest.mark.asyncio
async def test_member_joined_captcha_buttons_and_restrict(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await conn.handle_message(_msg(text="/captcha on", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))

    newbie = IncomingUser(id=NEW, first_name="تازه")
    service = IncomingMessage(chat=IncomingChat(id=CHAT), service="new_members")
    service.service_users = [newbie]
    await conn.handle_service(service)
    # محدودسازی + پیامِ دارای دکمه
    assert any(cid == CHAT and uid == NEW and muted for cid, uid, muted, _ in client.restricts)
    sent_with_buttons = [s for s in client.sends if s[3]]
    assert sent_with_buttons
    assert sent_with_buttons[0][3][0][0]["data"].startswith("captcha:")


@pytest.mark.asyncio
async def test_callback_answer_unrestricts(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    await conn.handle_message(_msg(text="/captcha on", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))
    newbie = IncomingUser(id=NEW, first_name="تازه")
    service = IncomingMessage(chat=IncomingChat(id=CHAT), service="new_members")
    service.service_users = [newbie]
    await conn.handle_service(service)

    state = host.cache.get(f"captcha:{CHAT}:{NEW}")
    assert state is not None
    cb = IncomingCallback(
        id="cb1", data=f"captcha:{CHAT}:{NEW}:{state['answer']}",
        chat=IncomingChat(id=CHAT), user=newbie)
    await conn.handle_callback(cb)
    # رفع محدودیت + پاسخ دکمه
    assert any(cid == CHAT and uid == NEW and not muted
               for cid, uid, muted, _ in client.restricts)
    assert "cb1" in client.answered
    assert any("خوش آمدید" in t for _, t, _, _ in client.sends)


# ═══ فرمان‌های تنبیه → اکشن فیزیکی ─────────────────────────────────
@pytest.mark.asyncio
async def test_moderation_physical_actions(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    admin = IncomingUser(id=ADMIN, first_name="ادمین")
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)

    await conn.handle_message(_msg(text="/mute 555 اسپم", user=admin))
    assert any(cid == CHAT and uid == TARGET and muted
               for cid, uid, muted, _ in client.restricts)
    await conn.handle_message(_msg(text="/ban 555 اسپم", user=admin))
    assert any(cid == CHAT and uid == TARGET for cid, uid in client.bans)
    await conn.handle_message(_msg(text="/kick 555 اسپم", user=admin))
    assert any(cid == CHAT and uid == TARGET for cid, uid in client.kicks)
    await conn.handle_message(_msg(text="/unmute 555", user=admin))
    assert any(cid == CHAT and uid == TARGET and not muted
               for cid, uid, muted, _ in client.restricts)


# ═══ ارتقا/عزل → اکشن فیزیکی + کانال لاگ ───────────────────────────
@pytest.mark.asyncio
async def test_promote_demote_and_log_channel(e2e):
    host, d, *_ = e2e
    _, _, _, roles, client, conn = _conn(e2e)
    owner = IncomingUser(id=OWNER, first_name="مالک")
    roles.set_role(CHAT, ADMIN, "admin", by_user=OWNER)
    # کانال لاگ تنظیم کن
    await conn.handle_message(_msg(text="/setlog -100987", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))
    # ارتقا توسط ادمین (بالاتر از mod)
    await conn.handle_message(_msg(text="/promote mod 55", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))
    assert any(cid == CHAT and uid == 55 and role == "mod"
               for cid, uid, role in client.promotes)
    # یک اکشن تنبیهی → خط لاگ به کانال
    await conn.handle_message(_msg(text="/ban 555 اسپم", user=IncomingUser(
        id=ADMIN, first_name="ادمین")))
    assert any(cid == LOG_CHANNEL and "بن" in text
               for cid, text, _, _ in client.sends)
    # عزل
    await conn.handle_message(_msg(text="/demote 55", user=IncomingUser(
        id=OWNER, first_name="مالک")))
    assert any(cid == CHAT and uid == 55 for cid, uid in client.demotes)
