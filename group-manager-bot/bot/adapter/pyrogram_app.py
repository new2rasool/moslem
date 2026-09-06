"""لایهٔ Pyrogram — تبدیل آپدیت‌های واقعی تلگرام به مدل‌های کانکتور.

این فایل تنها جایی است که pyrogram ایمپورت می‌شود (اختیاری/لِیزی)؛ بقیهٔ
هسته و کانکتور بدون آن کار می‌کنند. با «--run» (و BOT_TOKEN/API_ID/API_HASH)
فعال می‌شود.

اجرا:
    pip install pyrogram
    BOT_TOKEN=… API_ID=… API_HASH=… python -m bot.main --run [--watch]
"""

from __future__ import annotations

import asyncio
import logging

from bot.adapter.connector import TelegramConnector
from bot.adapter.models import (
    IncomingCallback,
    IncomingChat,
    IncomingMessage,
    IncomingUser,
)

log = logging.getLogger("adapter.pyrogram")

# نگاشت فیلدهای پیام → content_type هسته (کپیِ عمدیِ ساده)
_CONTENT_FIELDS = (
    ("photo", "photo"), ("video", "video"), ("animation", "animation"),
    ("document", "document"), ("voice", "voice"), ("video_note", "video_note"),
    ("sticker", "sticker"), ("audio", "audio"), ("poll", "poll"),
)


class PyrogramApp:
    """اتصال کامل: Client + هندلرها + حلقهٔ تیک میزبان."""

    def __init__(self, cfg, host, dispatcher, *, workdir: str) -> None:
        self.cfg = cfg
        self.host = host
        self.dispatcher = dispatcher
        self.workdir = workdir
        self.connector = TelegramConnector(host, dispatcher, client=None,
                                           default_lang=cfg.default_lang)
        self._bot_id: int | None = None

    # ── ساخت کلاینت و هندلرها ───────────────────────────────────────
    def _build_client(self):
        from pyrogram import Client  # noqa: PLC0415 (ایمپورت اختیاری)

        return Client(
            "group_manager_bot",
            api_id=self.cfg.api_id,
            api_hash=self.cfg.api_hash,
            bot_token=self.cfg.bot_token,
            workdir=self.workdir,
        )

    def _wire_client(self, client) -> None:
        """اتصال کانکتور به کلاینت واقعی + ثبت هندلرها."""
        self.connector.client = client
        self._register_handlers(client)

    # ── تبدیل آپدیت → مدل ───────────────────────────────────────────
    def _user(self, u) -> IncomingUser | None:
        if u is None:
            return None
        return IncomingUser(id=u.id, first_name=u.first_name or "",
                            last_name=u.last_name or "",
                            username=u.username or "", is_bot=bool(getattr(u, "is_bot", False)))

    def _chat(self, chat, private: bool) -> IncomingChat:
        return IncomingChat(id=chat.id if chat else 0,
                            title=(chat.title if chat else "") or "",
                            is_private=private)

    def _to_message(self, m, private: bool) -> IncomingMessage:
        chat = self._chat(m.chat, private)
        reply_id = reply_uid = None
        reply_name = ""
        if m.reply_to_message is not None:
            reply_id = m.reply_to_message.id
            ru = m.reply_to_message.from_user
            if ru is not None:
                reply_uid = ru.id
                reply_name = ((ru.first_name or "") + " " + (ru.last_name or "")).strip()
        ctype = ""
        for attr, label in _CONTENT_FIELDS:
            if getattr(m, attr, None) is not None:
                ctype = label
                break
        forwarded = bool(getattr(m, "forward_from", None)
                         or getattr(m, "forward_from_chat", None)
                         or getattr(m, "forward_sender_name", None)
                         or getattr(m, "forward_date", None))
        fwd_chat = getattr(m, "forward_from_chat", None)
        return IncomingMessage(
            id=m.id,
            chat=chat,
            user=self._user(m.from_user),
            text=(m.text or m.caption or ""),
            content_type=ctype,
            forwarded=forwarded,
            forward_from_chat_id=fwd_chat.id if fwd_chat is not None else None,
            reply_to_message_id=reply_id,
            reply_to_user_id=reply_uid,
            reply_to_user_name=reply_name,
        )

    def _register_handlers(self, client) -> None:
        from pyrogram import enums, filters  # noqa: PLC0415

        @client.on_message()
        async def _on_message(_c, message):
            try:
                private = bool(message.chat and
                               message.chat.type == enums.ChatType.PRIVATE)
                chat = message.chat
                # ── پیام‌های سرویس ──
                if message.new_chat_members:
                    m = IncomingMessage(id=message.id, chat=self._chat(chat, private),
                                        service="new_members")
                    m.service_users = [self._user(x) for x in message.new_chat_members
                                       if x is not None and x.id != self._bot_id]
                    if m.service_users:
                        await self.connector.handle_service(m)
                    return
                if message.left_chat_member is not None:
                    left = message.left_chat_member
                    if left.id == self._bot_id:
                        return  # خودِ ربات خارج شد — کاری نکن
                    m = IncomingMessage(id=message.id, chat=self._chat(chat, private),
                                        service="left_member",
                                        service_user=self._user(left))
                    await self.connector.handle_service(m)
                    return
                if message.from_user is None:
                    return  # پست کانال/بینام
                await self.connector.handle_message(self._to_message(message, private))
            except Exception:  # noqa: BLE001
                log.exception("خطا در پردازش پیام تلگرام")

        @client.on_callback_query()
        async def _on_callback(_c, query):
            try:
                private = bool(query.message and query.message.chat
                               and query.message.chat.type == enums.ChatType.PRIVATE)
                chat = self._chat(query.message.chat if query.message else None, private)
                cb = IncomingCallback(
                    id=str(getattr(query, "id", "") or ""),
                    data=str(getattr(query, "data", "") or ""),
                    chat=chat,
                    user=self._user(query.from_user),
                    message_id=query.message.id if query.message else None,
                )
                await self.connector.handle_callback(cb)
            except Exception:  # noqa: BLE001
                log.exception("خطا در پردازش دکمهٔ تلگرام")

    # ── اجرا ────────────────────────────────────────────────────────
    def run(self, watch: bool = False, tick_interval_s: float = 2.0) -> int:
        import pyrogram  # noqa: PLC0415

        client = self._build_client()
        self._wire_client(client)

        async def _main() -> None:
            await client.start()
            me = await client.get_me()
            self._bot_id = me.id
            log.info("ربات %s متصل شد (id=%s)", me.first_name, me.id)

            watcher = None
            if watch:
                watcher = asyncio.get_running_loop().create_task(
                    self.host.watch_loop(1.0))
                print("👀 نظارت بر پوشهٔ پلاگین‌ها فعال است (هات‌ری‌لود)")
            await self.host.start_background(tick_interval_s)
            print("✅ ربات پلاگین‌محور در حال اجراست (Ctrl+C برای توقف).")
            try:
                await pyrogram.idle()
            finally:
                await self.host.stop_background()
                if watcher:
                    watcher.cancel()
                await client.stop()

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            print("\n⏹ توقف ربات.")
        return 0
