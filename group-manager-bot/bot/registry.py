"""
ثبت‌نام فرمان‌ها/رویدادها/دکمه‌ها (Registry) — قلب پلاگین‌محور بودن.

هسته هیچ فرمانِ «قابلیتی» نمی‌شناسد؛ فقط ثبت‌نام‌ها را نگه می‌دارد و مسیر می‌دهد.
پلاگین‌ها هنگام بارگذاری، فرمان‌هایشان را این‌جا ثبت می‌کنند و هنگام حذف/ری‌لود،
همهٔ ردپایشان یک‌جا پاک می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from bot.context import CallbackContext, CommandContext, EventContext
from bot.domain.roles import AccessLevel

CommandHandler = Callable[[CommandContext], Awaitable[Any]]
EventHandler = Callable[[EventContext], Awaitable[Any]]
CallbackHandler = Callable[[CallbackContext], Awaitable[Any]]

# ── نام رویدادهای استاندارد (در فازهای بعدی گسترش می‌یابد) ───────────
EVENT_MEMBER_JOINED = "member_joined"
EVENT_MEMBER_LEFT = "member_left"

CORE_PLUGIN = "<core>"  # نام ثبت‌نامیِ فرمان‌های سیستم (میزبان خود هسته)


@dataclass
class CommandBinding:
    name: str
    handler: CommandHandler
    level: AccessLevel = AccessLevel.USER
    aliases: tuple[str, ...] = ()
    group_only: bool = False
    private_only: bool = False
    usage: str = ""
    help_key: str = ""
    plugin: str = CORE_PLUGIN


@dataclass
class EventBinding:
    event: str
    handler: EventHandler
    priority: int = 100  # بالاتر = زودتر اجرا می‌شود
    plugin: str = CORE_PLUGIN
    seq: int = 0


@dataclass
class CallbackBinding:
    prefix: str  # مثل "greeter:"
    handler: CallbackHandler
    plugin: str = CORE_PLUGIN


class CommandConflictError(ValueError):
    """دو پلاگین فرمان/نام مستعار تکراری ثبت کردند."""


class Registry:
    """ثبت‌نام‌های فعال + جدول جستجوی نام مستعار."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandBinding] = {}
        self._aliases: dict[str, str] = {}          # alias.casefold() → command name
        self._events: dict[str, list[EventBinding]] = {}
        self._callbacks: list[CallbackBinding] = []
        self._seq = 0

    # ── ثبت‌نام ─────────────────────────────────────────────────────
    def add_command(self, binding: CommandBinding) -> None:
        if binding.name in self._commands:
            other = self._commands[binding.name].plugin
            raise CommandConflictError(
                f"فرمان «{binding.name}» قبلاً توسط پلاگین {other!r} ثبت شده است"
            )
        for alias in (binding.name, *binding.aliases):
            key = alias.casefold()
            if key in self._aliases:
                owner = self._aliases[key]
                raise CommandConflictError(
                    f"نام مستعار {alias!r} برای {binding.name!r} با فرمان {owner!r} تداخل دارد"
                )
        self._commands[binding.name] = binding
        for alias in (binding.name, *binding.aliases):
            self._aliases[alias.casefold()] = binding.name

    def add_event(self, binding: EventBinding) -> None:
        binding.seq = self._seq
        self._seq += 1
        lst = self._events.setdefault(binding.event, [])
        lst.append(binding)
        # اولویت بالاتر اول، و در اولویت یکسان ترتیب ثبت
        lst.sort(key=lambda b: (-b.priority, b.seq))

    def add_callback(self, binding: CallbackBinding) -> None:
        self._callbacks.append(binding)

    # ── جستجو ───────────────────────────────────────────────────────
    def lookup_alias(self, token: str) -> CommandBinding | None:
        name = self._aliases.get(token.casefold())
        if name is None:
            return None
        return self._commands[name]

    def command(self, name: str) -> CommandBinding | None:
        return self._commands.get(name)

    def commands(self) -> dict[str, CommandBinding]:
        return dict(self._commands)

    def events(self, kind: str) -> list[EventBinding]:
        return list(self._events.get(kind, []))

    def event_kinds(self) -> list[str]:
        return sorted(self._events)

    def callbacks(self) -> list[CallbackBinding]:
        # بلندترین prefix اول (تا «greeter:approve:» بر «greeter:» برنده شود)
        return sorted(self._callbacks, key=lambda c: len(c.prefix), reverse=True)

    def callback_for(self, raw_action: str) -> tuple[CallbackBinding, str] | None:
        for cb in self.callbacks():
            if raw_action.startswith(cb.prefix):
                payload = raw_action[len(cb.prefix) :]
                return cb, payload
        return None

    # ── حذف بر اساس پلاگین (برای unload/reload) ─────────────────────
    def remove_plugin(self, plugin: str) -> int:
        """حذف کامل ردپای یک پلاگین؛ برمی‌گرداند: تعداد فرمان‌های حذف‌شده."""
        removed = 0
        for name in [n for n, b in self._commands.items() if b.plugin == plugin]:
            del self._commands[name]
            removed += 1
        self._rebuild_aliases()
        for kind in list(self._events):
            before = len(self._events[kind])
            self._events[kind] = [b for b in self._events[kind] if b.plugin != plugin]
            if not self._events[kind]:
                del self._events[kind]
        self._callbacks = [c for c in self._callbacks if c.plugin != plugin]
        return removed

    def _rebuild_aliases(self) -> None:
        self._aliases.clear()
        for binding in self._commands.values():
            for alias in (binding.name, *binding.aliases):
                self._aliases[alias.casefold()] = binding.name

    def counts(self) -> dict[str, int]:
        return {
            "commands": len(self._commands),
            "events": sum(len(v) for v in self._events.values()),
            "callbacks": len(self._callbacks),
        }
