"""
Dispatcher — توزیع فرمان‌ها/رویدادها/دکمه‌ها روی پلاگین‌های ثبت‌شده.

مسئولیت‌ها:
  • تشخیص «آیا این پیام یک فرمان است» (پیشوند / ! . یا نام مستعار شناخته‌شده)
  • پارس نام مستعار (فارسی/انگلیسی/دوقلمه) و آرگومان‌ها
  • چک سطح دسترسی + محدودیت private/group
  • پخش رویدادها بین پلاگین‌ها با ترتیب اولویت
  • مسیریابی دکمه‌ها (callback) بر پایهٔ طولانی‌ترین prefix
  • ایزوله‌کردن خطا: خطای یک پلاگین بقیه را نمی‌شکند
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from bot.context import CallbackContext, CommandContext, EventContext
from bot.domain.roles import AccessLevel, LEVEL_LABELS_EN, LEVEL_LABELS_FA
from bot.i18n.loader import Translator
from bot.registry import CORE_PLUGIN, CommandBinding, Registry
from bot.services.access_service import AccessService

log = logging.getLogger("dispatcher")

PREFIXES = ("/", "!", ".")

LangResolver = Callable[[int | None, int | None, bool], str]
PluginEnabled = Callable[[int | None, str], bool]  # (chat_id, plugin) → فعال؟


class Dispatcher:
    def __init__(
        self,
        registry: Registry,
        access: AccessService,
        translator: Translator,
        default_lang: str = "fa",
        plugin_enabled: PluginEnabled | None = None,
        action_sink=None,
    ) -> None:
        self.registry = registry
        self.access = access
        self.translator = translator
        self.default_lang = default_lang
        self.plugin_enabled = plugin_enabled
        # دریافت «اکشن‌های ساختاریافته» تولیدشده توسط پلاگین‌ها (اجرای فیزیکی با آداپتور)
        self.action_sink = action_sink

    # ── ابزار ───────────────────────────────────────────────────────
    def _denied_text(self, lang: str, required: AccessLevel) -> str:
        labels = LEVEL_LABELS_FA if lang == "fa" else LEVEL_LABELS_EN
        return self.translator.t(lang, "cmd_denied", level=labels.get(required, required.name))

    # ── تشخیص و پارس فرمان ──────────────────────────────────────────
    def _looks_like_command(self, text: str) -> bool:
        words = text.strip().split()
        if not words:
            return False
        if words[0] and words[0][0] in PREFIXES:
            return True
        if len(words) >= 2 and self.registry.lookup_alias(" ".join(words[:2])) is not None:
            return True
        token = words[0][1:] if words[0] and words[0][0] in PREFIXES else words[0]
        return self.registry.lookup_alias(token) is not None

    def _parse(self, text: str) -> tuple[CommandBinding | None, str, bool]:
        """
        خروجی: (binding یا None، args، is_command_style)
        is_command_style یعنی پیام با پیشوند شروع شده (برای پیام «فرمان ناشناخته»).
        """
        stripped = text.strip()
        if not stripped:
            return None, "", False
        words = stripped.split()

        # نام دوقلمه («بن سراسری ۱۲۳»)
        if len(words) >= 2:
            two = " ".join(words[:2])
            if self.registry.lookup_alias(two) is not None:
                args = " ".join(words[2:])
                binding = self.registry.lookup_alias(two)
                assert binding is not None
                return binding, args, False

        first = words[0]
        style = bool(first and first[0] in PREFIXES)
        token = first[1:] if style else first
        binding = self.registry.lookup_alias(token)
        if binding is None:
            return None, "", style
        return binding, " ".join(words[1:]), style

    # ── توزیع فرمان ─────────────────────────────────────────────────
    async def try_dispatch_command(
        self,
        text: str,
        *,
        chat_id: int | None,
        user_id: int,
        is_private: bool = False,
        lang: str | None = None,
        sender_name: str = "",
        sender_username: str = "",
        reply_to_user_id: int | None = None,
        reply_to_user_name: str = "",
    ) -> list[str] | None:
        """
        تلاش برای اجرای یک فرمان.

        خروجی:
          None              → پیام اصلاً فرمان نبود (بدون پاسخ)
          list[str]         → پیام‌های پاسخی که باید ارسال شوند
        """
        if not self._looks_like_command(text):
            return None
        lang = lang or self.default_lang

        binding, args, style = self._parse(text)
        if binding is None:
            # فرمان‌سبک ولی ناشناخته
            return [self.translator.t(lang, "cmd_unknown")]

        # محدودیت‌های محل اجرا
        if binding.private_only and not is_private:
            return [self.translator.t(lang, "cmd_private_only")]
        if binding.group_only and (chat_id is None or is_private):
            return [self.translator.t(lang, "cmd_group_only")]

        # اگر پلاگین در این گروه غیرفعال باشد، فرمانش خاموش است (بی‌صدا)
        if (
            self.plugin_enabled is not None
            and chat_id is not None
            and binding.plugin != CORE_PLUGIN
            and not self.plugin_enabled(chat_id, binding.plugin)
        ):
            return None

        # سطح دسترسی
        actual = self.access.level(chat_id, user_id)
        if actual < binding.level:
            return [self._denied_text(lang, binding.level)]

        ctx = CommandContext(
            plugin=binding.plugin,
            command=binding.name,
            args=args,
            raw_text=text,
            user_id=user_id,
            chat_id=None if is_private else chat_id,
            is_private=is_private,
            lang=lang,
            sender_name=sender_name,
            sender_username=sender_username,
            reply_to_user_id=reply_to_user_id,
            reply_to_user_name=reply_to_user_name,
        )
        try:
            await binding.handler(ctx)
        except Exception:  # noqa: BLE001 — ایزوله‌سازی خطا
            log.exception("خطا در فرمان %s (پلاگین %s)", binding.name, binding.plugin)
            ctx.respond(self.translator.t(lang, "cmd_error"))
        self._flush_actions(chat_id, ctx)
        return ctx.outgoing

    def _flush_actions(self, chat_id: int | None, ctx) -> None:
        """اگر پلاگین «اکشن ساختاریافته» ثبت کرده باشد، به action_sink می‌دهد."""
        if self.action_sink is None or not ctx.actions:
            return
        for action in ctx.actions:
            try:
                self.action_sink(chat_id, action)
            except Exception:  # noqa: BLE001
                log.exception("action_sink ناموفق بود")

    # ── توزیع رویداد ────────────────────────────────────────────────
    async def dispatch_event(
        self,
        kind: str,
        *,
        chat_id: int | None,
        lang: str,
        user_id: int | None = None,
        user_name: str = "",
        user_username: str = "",
        data: dict | None = None,
    ) -> list[str]:
        """پخش یک رویداد بین همهٔ پلاگین‌های مشترک (به ترتیب اولویت)."""
        ctx = EventContext(
            kind=kind,
            chat_id=chat_id,
            lang=lang,
            user_id=user_id,
            user_name=user_name,
            user_username=user_username,
            data=data or {},
        )
        for binding in self.registry.events(kind):
            try:
                await binding.handler(ctx)
            except Exception:  # noqa: BLE001
                log.exception("خطا در رویداد %s (پلاگین %s)", kind, binding.plugin)
        self._flush_actions(chat_id, ctx)
        return ctx.outgoing

    # ── توزیع دکمه ──────────────────────────────────────────────────
    async def dispatch_callback(
        self,
        raw_action: str,
        *,
        chat_id: int | None,
        user_id: int,
        lang: str,
    ) -> list[str] | None:
        matched = self.registry.callback_for(raw_action)
        if matched is None:
            return None
        binding, payload = matched
        prefix = binding.prefix
        # هرچه بعد از prefix آمد = payload (می‌تواند شامل «:» باشد)
        action = payload.split(":")[0] if payload else ""
        ctx = CallbackContext(
            plugin=binding.plugin,
            prefix=prefix,
            action=action,
            payload=payload,
            raw_action=raw_action,
            user_id=user_id,
            chat_id=chat_id,
            lang=lang,
        )
        try:
            await binding.handler(ctx)
        except Exception:  # noqa: BLE001
            log.exception("خطا در دکمهٔ %s (پلاگین %s)", prefix, binding.plugin)
            ctx.respond(self.translator.t(lang, "cmd_error"))
        self._flush_actions(chat_id, ctx)
        return ctx.outgoing
