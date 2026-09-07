"""کانکتور تلگرام — پل بین دیسپچر/میزبان و یک کلاینت پیام‌رسان.

مستقل از تلگرام است: با «مدل‌های پیام» (adapter/models.py) و یک کلاینت
duck-typed کار می‌کند (send_message/delete_messages/restrict/ban/kick/…).
بنابراین تمام منطق اتصال بدون نصب Pyrogram و بدون اینترنت قابل تست است.

وظایف:
  ۱) تبدیل پیام/ورود/خروج/دکمه به رویدادهای هسته (دیسپچر)
  ۲) ارسال پاسخ‌های پلاگین‌ها + دکمه‌های شیشه‌ای (outbox)
  ۳) اجرای فیزیکی «اکشن‌های ساختاریافته» (delete/ban/mute/…)
  ۴) رساندن خطوط کانال لاگ (audit_sink) به کانال تنظیم‌شده با /setlog
"""

from __future__ import annotations

import asyncio
import logging

from bot.adapter.models import IncomingCallback, IncomingMessage

log = logging.getLogger("adapter.connector")

# نگاشت نوع رسانهٔ تلگرام → content_type هسته
_MEDIA_MAP = {
    "photo": "photo",
    "video": "video",
    "animation": "animation",
    "document": "document",
    "voice": "voice",
    "video_note": "video_note",
    "sticker": "sticker",
    "audio": "audio",
    "poll": "poll",
}


class TelegramConnector:
    """بدون وابستگی به تلگرام — کلاینت باید این متدها را داشته باشد:

    async send_message(chat_id, text, *, reply_to=None, buttons=None)
    async delete_messages(chat_id, message_id)
    async restrict(chat_id, user_id, *, muted, until=None)
    async ban(chat_id, user_id)
    async kick(chat_id, user_id)
    async lock_join(chat_id, locked)
    async promote(chat_id, user_id, role=None)
    async demote(chat_id, user_id)
    async answer_callback(callback_id, text="")
    """

    def __init__(self, host, dispatcher, client, *, default_lang: str = "fa") -> None:
        self.host = host
        self.dispatcher = dispatcher
        self.client = client
        self.default_lang = default_lang

        # سینک‌های خروجی: پلاگین‌ها (همگام) صدا می‌زنند ← صف (ناهمگام) اجرا می‌شود
        self.outbox: list[tuple[int, str, int | None, list | None]] = []
        self._pending_actions: list[tuple[int | None, dict]] = []
        self._current_message_id: int | None = None
        self._current_chat_id: int | None = None

        host.out_sink = self._sink_out
        host.action_sink = self._sink_action
        host.audit_sink = self._sink_audit
        dispatcher.action_sink = self._sink_action

    # ── سینک‌ها (همگام — از پلاگین‌ها صدا زده می‌شوند) ─────────────
    def _sink_out(self, chat_id, text) -> None:
        if text:
            self.outbox.append((int(chat_id), str(text), None, None))

    def _sink_action(self, chat_id, action) -> None:
        self._pending_actions.append((chat_id, dict(action)))

    def _sink_audit(self, chat_id, lines) -> None:
        dest = self._log_destination(chat_id)
        for line in lines:
            self.outbox.append((dest, str(line), None, None))

    def _log_destination(self, chat_id) -> int:
        group = self.host.groups.get(chat_id) if chat_id is not None else None
        channel = ""
        if group is not None:
            channel = str(group.settings.get("log_channel", "") or "").strip()
        ch = (channel or "").strip()
        try:
            return int(ch)
        except ValueError:
            pass
        # @channel نیاز به resolve دارد (در نسخهٔ بعدی) → خودِ گروه
        return int(chat_id) if chat_id is not None else 0

    def _lang(self, chat_id) -> str:
        if chat_id is not None:
            group = self.host.groups.get(chat_id)
            if group is not None:
                return group.lang or self.default_lang
        return self.default_lang

    # ── رسیدگی به آپدیت‌ها (از لایهٔ Pyrogram صدا زده می‌شوند) ───────
    async def handle_message(self, msg: IncomingMessage) -> None:
        """پیام معمولی (گروه/خصوصی): فرمان یا رویداد message.

        دو شناسهٔ مجزا:
          - scope_chat: برای دیسپچر/پلاگین‌ها (چت خصوصی = None چون «گروه» نیست)
          - send_chat:  مقصدِ واقعی ارسال پاسخ (همیشه شناسهٔ همان چت)
        باگِ قبلی: پاسخ به scope_chat می‌رفت؛ در چت خصوصی (None) ارسال بی‌صدا
        می‌شکست و ربات به دکمهٔ Start هیچ واکنشی نشان نمی‌داد.
        """
        scope_chat = None if msg.chat.is_private else msg.chat.id
        send_chat = int(msg.chat.id or 0)
        self._current_message_id = msg.id
        self._current_chat_id = send_chat
        lang = self._lang(scope_chat)
        text = msg.text or ""
        user = msg.user

        try:
            prev_keyboard = getattr(self.dispatcher, "last_keyboard", None)
            if text.strip():
                sends = await self.dispatcher.try_dispatch_command(
                    text,
                    chat_id=scope_chat,
                    user_id=user.id if user else 0,
                    is_private=msg.chat.is_private,
                    lang=lang,
                    sender_name=user.name if user else "",
                    sender_username=user.username if user else "",
                    reply_to_user_id=msg.reply_to_user_id,
                    reply_to_user_name=msg.reply_to_user_name,
                )
                if sends is not None:
                    # پیام یک فرمان بود → پاسخ + اکشن‌ها + دکمهٔ احتمالی
                    await self._dispatch_output(sends, send_chat,
                                                msg.reply_to_message_id,
                                                prev_keyboard)
                    await self._run_actions(send_chat)
                    await self._flush()
                    return

            ctype = _MEDIA_MAP.get(msg.content_type, "") or ""
            if not ctype and not text:
                await self._flush()
                return
            data = {
                "text": text,
                "content_type": ctype or "text",
                "sender_name": user.name if user else "",
                "sender_username": user.username if user else "",
            }
            if msg.forwarded or msg.forward_from_chat_id is not None:
                data["is_forward"] = True
            if msg.forward_from_chat_id is not None:
                data["forward_from_chat_id"] = msg.forward_from_chat_id
            sends = await self.dispatcher.dispatch_event(
                "message",
                chat_id=scope_chat,
                lang=lang,
                user_id=user.id if user else None,
                user_name=user.name if user else "",
                user_username=user.username if user else "",
                data=data,
            )
            if sends:
                await self._dispatch_output(sends, send_chat, None, prev_keyboard)
            await self._run_actions(send_chat)
            await self._flush()
        finally:
            self._current_message_id = None

    async def handle_service(self, msg: IncomingMessage) -> None:
        """پیام سرویس: ورود/خروج عضو."""
        scope_chat = None if msg.chat.is_private else msg.chat.id
        send_chat = int(msg.chat.id or 0)
        lang = self._lang(scope_chat)
        title = msg.chat.title or ""
        prev_keyboard = getattr(self.dispatcher, "last_keyboard", None)
        if msg.service == "new_members":
            for member in msg.service_users:
                sends = await self.dispatcher.dispatch_event(
                    "member_joined",
                    chat_id=scope_chat,
                    lang=lang,
                    user_id=member.id,
                    user_name=member.name,
                    user_username=member.username or "",
                    data={"member_id": member.id,
                          "member_name": member.name,
                          "member_username": member.username or "",
                          "member_bot": member.is_bot,
                          "chat_title": title,
                          "member_count": len(msg.service_users)},
                )
                if sends:
                    await self._dispatch_output(sends, send_chat, None,
                                                prev_keyboard)
        elif msg.service == "left_member" and msg.service_user is not None:
            member = msg.service_user
            sends = await self.dispatcher.dispatch_event(
                "member_left",
                chat_id=scope_chat,
                lang=lang,
                user_id=member.id,
                user_name=member.name,
                user_username=member.username or "",
                data={"member_id": member.id,
                      "member_name": member.name,
                      "member_username": member.username or "",
                      "chat_title": title},
            )
            if sends:
                await self._dispatch_output(sends, send_chat, None, prev_keyboard)
        await self._run_actions(send_chat)
        await self._flush()

    async def handle_callback(self, cb: IncomingCallback) -> None:
        scope_chat = None if cb.chat.is_private else cb.chat.id
        send_chat = int(cb.chat.id or 0)
        lang = self._lang(scope_chat)
        prev_keyboard = getattr(self.dispatcher, "last_keyboard", None)
        user = cb.user
        sends = await self.dispatcher.dispatch_callback(
            cb.data, chat_id=scope_chat,
            user_id=user.id if user else 0,
            lang=lang,
            sender_name=user.name if user else "",
            sender_username=user.username if user else "",
        )
        await self._run_actions(send_chat)
        if sends:
            await self._dispatch_output(sends, send_chat, None, prev_keyboard)
        if cb.user is not None and cb.id:
            try:
                await self.client.answer_callback(cb.id, text="")
            except Exception:  # noqa: BLE001
                log.exception("پاسخ callback ناموفق بود")
        await self._flush()

    # ── خروجی ───────────────────────────────────────────────────────
    def _take_keyboard(self, prev: list | None):
        """فقط اگر در همین پردازش صفحه‌کلید تازه‌ای ساخته شده، برمی‌گرداند."""
        kb = getattr(self.dispatcher, "last_keyboard", None)
        return kb if kb is not prev else None

    async def _dispatch_output(self, sends: list[str], chat_id, reply_to,
                               prev_keyboard: list | None = None) -> None:
        """ارسال پاسخ‌ها؛ آخرین پیام دکمه‌های صفحه‌کلیدِ همین پردازش را می‌گیرد."""
        buttons = self._take_keyboard(prev_keyboard)
        n = len(sends)
        for i, text in enumerate(sends):
            attach = buttons if i == n - 1 else None
            self.outbox.append((chat_id, text, reply_to, attach))

    async def _flush(self) -> None:
        """ارسال همهٔ پیام‌های صف‌شده (خروجی پلاگین‌ها + خطوط لاگ)."""
        items, self.outbox = self.outbox, []
        for chat_id, text, reply_to, buttons in items:
            if not text:
                continue
            try:
                await self.client.send_message(
                    chat_id, text, reply_to=reply_to, buttons=buttons)
            except Exception:  # noqa: BLE001
                log.exception("ارسال پیام به %s ناموفق بود", chat_id)

    # ── اجرای اکشن‌های ساختاریافته ─────────────────────────────────
    async def _run_actions(self, chat_id) -> None:
        items, self._pending_actions = self._pending_actions, []
        for action_chat, a in items:
            cid = action_chat if action_chat is not None else chat_id
            if cid is None:
                continue
            kind = a.get("type")
            uid = a.get("user_id")
            try:
                if kind == "delete_message":
                    if self._current_message_id:
                        await self.client.delete_messages(cid, self._current_message_id)
                elif kind in ("restrict", "mute"):
                    await self.client.restrict(cid, uid, muted=True,
                                               until=a.get("seconds"))
                elif kind in ("unrestrict", "unmute"):
                    await self.client.restrict(cid, uid, muted=False)
                elif kind == "ban":
                    await self.client.ban(cid, uid)
                elif kind == "kick":
                    await self.client.kick(cid, uid)
                elif kind == "lock_join":
                    await self.client.lock_join(cid, True)
                elif kind == "unlock_join":
                    await self.client.lock_join(cid, False)
                elif kind == "promote":
                    await self.client.promote(cid, uid, role=a.get("role"))
                elif kind == "demote":
                    await self.client.demote(cid, uid)
                else:
                    log.warning("اکشن ناشناخته از پلاگین: %s", kind)
            except Exception:  # noqa: BLE001
                log.exception("اجرای اکشن %s در گروه %s ناموفق بود", kind, cid)
