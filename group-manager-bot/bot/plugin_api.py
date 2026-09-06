"""
PluginAPI — سطح دسترسیِ (API) پایداری که به هر پلاگین داده می‌شود.

پلاگین فقط با همین شیء کار می‌کند: ثبت فرمان/رویداد/دکمه، ترجمهٔ اختصاصی،
دسترسی به سرویس‌های هسته (cfg/access/cache/repos). هیچ پلاگینی نباید مستقیم
به داخل هسته (registry/dispatcher/…) دست بزند؛ همین مرز اجازه می‌دهد هسته
بدون شکستن پلاگین‌ها تکامل یابد.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from bot.context import CallbackContext, CommandContext, EventContext
from bot.domain.roles import AccessLevel
from bot.i18n.loader import Translator

if TYPE_CHECKING:  # pragma: no cover — فقط برای تایپ
    from bot.cache.cache import Cache
    from bot.config import Config
    from bot.registry import (
        CallbackHandler,
        CommandHandler,
        EventHandler,
        Registry,
    )
    from bot.repositories.base import GroupRepo, RoleRepo, UserRepo
    from bot.services.access_service import AccessService


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class PluginTranslator:
    """
    ترجمهٔ حوزهٔ پلاگین: اول متن خودِ پلاگین (locales/fa.json…) بعد fallback
    به متن‌های پایهٔ هسته (برای کلیدهایی مثل level_* و پیام‌های سیستم).
    """

    def __init__(self, base: Translator, own: dict[str, dict[str, str]]) -> None:
        self._base = base
        self._own = own

    def t(self, lang: str, key: str, **fmt: Any) -> str:
        own_lang = self._own.get(lang) or self._own.get("en") or {}
        if key in own_lang:
            text = own_lang[key]
        else:
            text = self._base.text(lang, key)
        if fmt:
            return text.format_map(_SafeDict(fmt))
        return text


class PluginAPI:
    """API که در تابع register(api) هر پلاگین تحویل داده می‌شود."""

    def __init__(
        self,
        *,
        name: str,
        version: str,
        cfg: "Config",
        translator: PluginTranslator,
        registry: "Registry",
        access: "AccessService",
        cache: "Cache",
        groups: "GroupRepo",
        users: "UserRepo",
        roles: "RoleRepo",
        source_dir: Path,
    ) -> None:
        self.name = name
        self.version = version
        self.cfg = cfg
        self._translator = translator
        self.access = access
        self.cache = cache
        self.groups = groups
        self.users = users
        self.roles = roles
        self.source_dir = source_dir
        self._registry = registry
        self._log = logging.getLogger(f"plugin.{name}")
        # در ادامه توسط PluginHost مقداردهی می‌شود (برای فرمان‌های مدیریتی)
        self.host: Any = None

    @property
    def log(self) -> logging.Logger:
        return self._log

    def tr(self, lang: str, key: str, **fmt: Any) -> str:
        """ترجمهٔ حوزهٔ پلاگین (کلیدهای خودِ پلاگین، سپس fallback به هسته)."""
        return self._translator.t(lang, key, **fmt)

    # ── ثبت فرمان ───────────────────────────────────────────────────
    def register_command(
        self,
        name: str,
        handler: "CommandHandler",
        *,
        level: AccessLevel = AccessLevel.USER,
        aliases: tuple[str, ...] = (),
        group_only: bool = False,
        private_only: bool = False,
        usage: str = "",
        help_key: str = "",
    ) -> None:
        """ثبت یک فرمان متنی. «name» نام یکتا (لاتین)، aliases شامل فارسی/انگلیسی."""
        from bot.registry import CommandBinding

        self._registry.add_command(
            CommandBinding(
                name=name,
                handler=handler,
                level=level,
                aliases=aliases,
                group_only=group_only,
                private_only=private_only,
                usage=usage,
                help_key=help_key,
                plugin=self.name,
            )
        )
        self._log.info("فرمان ثبت شد: %s (سطح %s)", name, level.name)

    # ── ثبت رویداد ──────────────────────────────────────────────────
    def register_event(
        self,
        event: str,
        handler: "EventHandler",
        *,
        priority: int = 100,
    ) -> None:
        from bot.registry import EventBinding

        self._registry.add_event(
            EventBinding(event=event, handler=handler, priority=priority, plugin=self.name)
        )
        self._log.info("رویداد ثبت شد: %s (اولویت %s)", event, priority)

    # ── ثبت دکمه (callback) ─────────────────────────────────────────
    def register_callback(self, prefix: str, handler: "CallbackHandler") -> None:
        """prefix باید به «:» ختم شود و یکتا باشد (مثل 'greeter:' یا 'greeter:confirm:')."""
        from bot.registry import CallbackBinding

        if not prefix.endswith(":"):
            prefix = prefix + ":"
        self._registry.add_callback(
            CallbackBinding(prefix=prefix, handler=handler, plugin=self.name)
        )
        self._log.info("دکمه ثبت شد: %s", prefix)
