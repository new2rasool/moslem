"""
PluginHost — بارگذار پویا و خودکار پلاگین‌ها.

کشف:
    plugins/<name>/plugin.py          ← هر پوشه یک پلاگین
    plugins/<name>.py                 ← یا یک فایل تکی

قرارداد هر پلاگین:
    PLUGIN_VERSION = "1.0.0"                        (اختیاری، پیش‌فرض "0.1.0")
    def register(api: PluginAPI) -> None: ...        (الزامی)
    def on_unload() -> None: ...                     (اختیاری)

ترجمهٔ اختصاصی پلاگین:  plugins/<name>/locales/{fa,en}.json

نکتهٔ کلیدی: افزودن/به‌روزرسانی پلاگین = افزودن/جایگزینی فایل در پوشهٔ plugins؛
هسته هیچ تغییری نمی‌کند. `reload_changed()` (و watcher) تفاوت‌ها را می‌یابد و
پلاگینِ تازه/تغییریافته را بدون ری‌استارت بارگذاری/جایگزین می‌کند.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bot.i18n.loader import Translator
from bot.plugin_api import PluginAPI, PluginTranslator

if TYPE_CHECKING:  # pragma: no cover
    from bot.cache.cache import Cache
    from bot.config import Config
    from bot.registry import Registry
    from bot.repositories.base import (
        ActionRepo,
        GroupRepo,
        RoleRepo,
        UserRepo,
        WarnRepo,
    )
    from bot.services.access_service import AccessService

log = logging.getLogger("pluginhost")

PLUGIN_FILE = "plugin.py"
SUPPORTED_LOCALES = ("fa", "en")


@dataclass
class PluginRecord:
    name: str
    version: str
    source_path: Path
    enabled: bool = False
    failed: bool = False
    error: str = ""
    commands: int = 0
    events: int = 0
    callbacks: int = 0
    api: PluginAPI | None = None
    module: Any = None  # شیء ماژول بارگذاری‌شده (برای on_tick/on_unload)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PluginHost:
    """میزبان پلاگین‌ها: کشف ← بارگذاری ← ثبت ← نظارت بر تغییرات."""

    def __init__(
        self,
        *,
        cfg: "Config",
        plugins_dir: Path,
        translator: Translator,
        registry: "Registry",
        access: "AccessService",
        cache: "Cache",
        groups: "GroupRepo",
        users: "UserRepo",
        roles: "RoleRepo",
        warns: "WarnRepo | None" = None,
        actions: "ActionRepo | None" = None,
    ) -> None:
        self.cfg = cfg
        self.plugins_dir = plugins_dir
        self.translator = translator
        self.registry = registry
        self.access = access
        self.cache = cache
        self.groups = groups
        self.users = users
        self.roles = roles
        self.warns = warns
        self.actions = actions
        self.records: dict[str, PluginRecord] = {}
        self._hashes: dict[str, str] = {}  # path → sha256
        self._running = False
        # هدفِ رویدادهای داخلی (مثل action_recorded) — آداپتور/تست آن را ست می‌کند
        self.audit_sink: Any = None
        # سینک ارسال پیام به گروه و سینک اکشن فیزیکی (آداپتور تلگرام/تست)
        self.out_sink: Any = None
        self.action_sink: Any = None
        self._tick_task: asyncio.Task | None = None
        self._register_core_commands()

    # ── خروجی‌های سطح میزبان (برای پلاگین‌ها و وظایف پس‌زمینه) ───────
    def send_text(self, chat_id: int | None, text: str) -> None:
        """ارسال پیام به یک گروه (از طریق آداپتور out_sink)."""
        if not text:
            return
        if self.out_sink is not None:
            try:
                self.out_sink(chat_id, text)
            except Exception:  # noqa: BLE001
                log.exception("out_sink ناموفق بود")

    def push_action(self, chat_id: int | None, action: dict) -> None:
        """ثبت یک اکشن فیزیکی خارج از Context (مثل اخراج کپچای منقضی)."""
        if self.action_sink is not None:
            try:
                self.action_sink(chat_id, action)
            except Exception:  # noqa: BLE001
                log.exception("action_sink (host) ناموفق بود")

    # ── تیک دوره‌ای برای کارهای پس‌زمینهٔ پلاگین‌ها (on_tick) ───────
    async def tick(self) -> None:
        """یک بار اجرای on_tick همهٔ پلاگین‌های فعال (تمیزکاری/زمان‌سنجی)."""
        for name in list(self.records):
            rec = self.records.get(name)
            if rec is None or not rec.enabled or rec.module is None or rec.api is None:
                continue
            fn = getattr(rec.module, "on_tick", None)
            if not callable(fn):
                continue
            try:
                await fn(rec.api)
            except Exception:  # noqa: BLE001
                log.exception("on_tick پلاگین %s ناموفق بود", name)

    async def start_background(self, interval_s: float = 2.0) -> None:
        """حلقهٔ پس‌زمینهٔ میزبان (در --run/--watch). پلاگین‌ها با on_tick شرکت می‌کنند."""
        if self._tick_task is not None:
            return
        self._running = True

        async def _loop() -> None:
            while self._running:
                try:
                    await self.tick()
                except Exception:  # noqa: BLE001
                    log.exception("خطا در تیک میزبان")
                await asyncio.sleep(interval_s)

        self._tick_task = asyncio.create_task(_loop())

    async def stop_background(self) -> None:
        self._running = False
        if self._tick_task is not None:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

    # ── انتشار رویداد داخلی (برای پلاگین‌ها — مثل action_recorded) ───
    async def emit(
        self,
        kind: str,
        *,
        chat_id: int | None = None,
        lang: str = "fa",
        user_id: int | None = None,
        user_name: str = "",
        user_username: str = "",
        data: dict | None = None,
    ) -> list[str]:
        """اجرای شنونده‌های یک رویداد داخلی؛ برمی‌گرداند پیام‌های تولیدشده.

        برخلاف رویدادهای بیرونی (که آداپتور صدا می‌زند)، این یکی درون هسته برای
        پلاگین‌های هم‌کار استفاده می‌شود و پلاگین‌های غیرفعالِ همان گروه را رد می‌کند.
        """
        from bot.context import EventContext
        from bot.registry import CORE_PLUGIN

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
            if chat_id is not None and binding.plugin != CORE_PLUGIN:
                if not self.is_plugin_enabled(chat_id, binding.plugin):
                    continue
            try:
                await binding.handler(ctx)
            except Exception:  # noqa: BLE001
                log.exception("خطا در رویداد داخلی %s (پلاگین %s)", kind, binding.plugin)
        return ctx.outgoing

    # ── فعال/غیرفعال بودن پلاگین در هر گروه (تنظیمات گروه) ──────────
    def is_plugin_enabled(self, chat_id: int | None, plugin: str) -> bool:
        """پیش‌فرض: فعال؛ مدیر می‌تواند در settings['plugins'][name] خاموشش کند."""
        if chat_id is None:
            return True
        group = self.groups.get(chat_id)
        if group is None:
            return True
        return group.settings.get("plugins", {}).get(plugin, True)

    def set_plugin_enabled(self, chat_id: int, plugin: str, enabled: bool) -> None:
        if plugin not in self.records and plugin != "<core>":
            raise KeyError(plugin)
        group = self.groups.get(chat_id)
        from bot.repositories.base import Group

        if group is None:
            group = Group(chat_id=chat_id, settings={})
        plugins = dict(group.settings.get("plugins", {}))
        plugins[plugin] = bool(enabled)
        group.settings["plugins"] = plugins
        self.groups.upsert(group)

    # ── فرمان‌های سیستمی میزبان (خودِ هسته) ─────────────────────────
    def _register_core_commands(self) -> None:
        from bot import __version__
        from bot.host_system import register_core
        from bot.registry import CORE_PLUGIN

        core_api = PluginAPI(
            name=CORE_PLUGIN,
            version=__version__,
            cfg=self.cfg,
            translator=PluginTranslator(self.translator, {}),
            registry=self.registry,
            access=self.access,
            cache=self.cache,
            groups=self.groups,
            users=self.users,
            roles=self.roles,
            warns=self.warns,
            actions=self.actions,
            source_dir=self.plugins_dir,
        )
        core_api.host = self
        self._core_api = core_api
        register_core(core_api)

    # ── کشف ─────────────────────────────────────────────────────────
    def discover(self) -> list[Path]:
        """مسیر پلاگین‌های موجود (پوشه دارای plugin.py یا فایل .py تکی)."""
        found: list[Path] = []
        if not self.plugins_dir.exists():
            return found
        for child in sorted(self.plugins_dir.iterdir()):
            if child.is_dir():
                candidate = child / PLUGIN_FILE
                if candidate.is_file():
                    found.append(candidate)
            elif child.is_file() and child.suffix == ".py" and child.stem != "__init__":
                found.append(child)
        return found

    @staticmethod
    def _plugin_name(path: Path) -> str:
        return path.parent.name if path.name == PLUGIN_FILE else path.stem

    # ── بارگذاری ────────────────────────────────────────────────────
    def load_all(self) -> list[str]:
        """بارگذاری همهٔ پلاگین‌های کشف‌شده؛ برمی‌گرداند نام پلاگین‌های فعال."""
        loaded: list[str] = []
        for path in self.discover():
            self._hashes[str(path)] = _file_hash(path)
            name = self._load_one(path)
            if name:
                loaded.append(name)
        return loaded

    def load(self, name: str) -> bool:
        """بارگذاری یک پلاگین مشخص (برای مدیریت runtime)."""
        for path in self.discover():
            if self._plugin_name(path) == name:
                self._hashes[str(path)] = _file_hash(path)
                return self._load_one(path) is not None
        return False

    def _load_one(self, path: Path) -> str | None:
        name = self._plugin_name(path)
        try:
            module = self._import_module(name, path)
            api = self._build_api(name, path, module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise ValueError("پلاگین باید تابع register(api) تعریف کند")
            register(api)
            record = PluginRecord(
                name=name,
                version=str(getattr(module, "PLUGIN_VERSION", "0.1.0")),
                source_path=path,
                enabled=True,
                commands=sum(
                    1 for b in self.registry.commands().values() if b.plugin == name
                ),
                events=sum(
                    1
                    for kind in self.registry.event_kinds()
                    for b in self.registry.events(kind)
                    if b.plugin == name
                ),
                callbacks=sum(1 for c in self.registry.callbacks() if c.plugin == name),
                api=api,
                module=module,
            )
            self.records[name] = record
            log.info("پلاگین بارگذاری شد: %s v%s (%s فرمان)", name, record.version, record.commands)
            return name
        except Exception as exc:  # noqa: BLE001 — خطای یک پلاگین بقیه را نمی‌شکند
            record = PluginRecord(
                name=name, version="?", source_path=path, failed=True, error=str(exc)
            )
            self.records[name] = record
            log.error("پلاگین %s ناموفق بود: %s", name, exc)
            return None

    def _import_module(self, name: str, path: Path) -> Any:
        """
        اجرای ماژول پلاگین مستقیم از سورس.

        عمداً از importlib.abc از طریق spec استفاده نمی‌شود؛ چون کش بایت‌کد پایتون
        (__pycache__) در بازنویسی‌های سریعِ هم‌سایز، فایل کهنه را برمی‌گرداند و
        هات‌ری‌لود را می‌شکند. کامپایل صریح هر بار از محتوای فعلی فایل انجام می‌شود.
        """
        import types

        module_name = f"gmb_plugin_{name}"
        sys.modules.pop(module_name, None)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ImportError(f"نمی‌توان فایل پلاگین {path} را خواند: {exc}") from exc
        code = compile(source, str(path), "exec")
        module = types.ModuleType(module_name)
        module.__file__ = str(path)
        module.__package__ = ""
        module.__name__ = module_name
        sys.modules[module_name] = module
        exec(code, module.__dict__)
        return module

    def _build_api(self, name: str, path: Path, module: Any) -> PluginAPI:
        source_dir = path.parent
        own = self._load_plugin_locales(source_dir)
        api = PluginAPI(
            name=name,
            version=str(getattr(module, "PLUGIN_VERSION", "0.1.0")),
            cfg=self.cfg,
            translator=PluginTranslator(self.translator, own),
            registry=self.registry,
            access=self.access,
            cache=self.cache,
            groups=self.groups,
            users=self.users,
            roles=self.roles,
            warns=self.warns,
            actions=self.actions,
            source_dir=source_dir,
        )
        api.host = self
        return api

    @staticmethod
    def _load_plugin_locales(source_dir: Path) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        locales = source_dir / "locales"
        if locales.is_dir():
            for lang in SUPPORTED_LOCALES:
                file = locales / f"{lang}.json"
                if file.is_file():
                    try:
                        data = json.loads(file.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            out[lang] = {str(k): str(v) for k, v in data.items()}
                    except ValueError as exc:
                        log.warning("لوکال %s پلاگین خراب است: %s", file, exc)
        return out

    # ── حذف / ری‌لود ────────────────────────────────────────────────
    def unload(self, name: str) -> bool:
        """حذف کامل پلاگین (فرمان‌ها/رویدادها/دکمه‌ها) از هسته."""
        record = self.records.pop(name, None)
        if record is None:
            return False
        removed = self.registry.remove_plugin(name)
        module = record.module
        if module is not None:
            hook = getattr(module, "on_unload", None)
            if callable(hook):
                try:
                    hook(record.api)
                except Exception:  # noqa: BLE001
                    log.exception("on_unload پلاگین %s ناموفق بود", name)
        log.info("پلاگین حذف شد: %s (%s فرمان)", name, removed)
        return True

    def reload(self, name: str) -> bool:
        """حذف و بارگذاری دوبارهٔ یک پلاگین."""
        was_loaded = self.unload(name)
        path = None
        for p in self.discover():
            if self._plugin_name(p) == name:
                path = p
                break
        if path is None:
            return was_loaded
        self._hashes[str(path)] = _file_hash(path)
        return self._load_one(path) is not None

    def enabled_names(self) -> list[str]:
        return sorted(n for n, r in self.records.items() if r.enabled)

    def failed_names(self) -> list[str]:
        return sorted(n for n, r in self.records.items() if r.failed)

    # ── ری‌لود خودکار (تفاوت‌یاب) ───────────────────────────────────
    def reload_changed(self) -> list[str]:
        """
        پوشهٔ پلاگین‌ها را با آخرین وضعیت مقایسه و تغییرات را اعمال می‌کند:
          • فایل جدید       → بارگذاری
          • فایل تغییرکرده  → unload + بارگذاری دوباره
          • فایل حذف‌شده     → unload
        بدون هیچ تغییری در هسته. برمی‌گرداند نام پلاگین‌های دست‌خورده.
        """
        touched: list[str] = []
        current = {str(p): p for p in self.discover()}

        # حذف‌شده‌ها
        for path_str in list(self._hashes):
            if path_str not in current:
                name = self._plugin_name(Path(path_str))
                self._hashes.pop(path_str, None)
                self.unload(name)
                touched.append(name)

        # تازه‌ها و تغییرکرده‌ها
        for path_str, path in current.items():
            new_hash = _file_hash(path)
            old_hash = self._hashes.get(path_str)
            name = self._plugin_name(path)
            if old_hash is None:
                # پلاگین تازه — حتی اگر بارگذاری ناموفق باشد، «دست‌خورده» محسوب می‌شود
                self._hashes[path_str] = new_hash
                self._load_one(path)
                touched.append(name)
            elif old_hash != new_hash:
                self._hashes[path_str] = new_hash
                self.unload(name)
                self._load_one(path)
                touched.append(name)
        return touched

    # ── Watcher برای اجرای زنده ─────────────────────────────────────
    async def watch_loop(self, interval_s: float = 1.0) -> None:
        """چرخهٔ نظارت — در main --watch روشن می‌شود."""
        self._running = True
        log.info("نظارت بر پوشهٔ پلاگین‌ها شروع شد: %s", self.plugins_dir)
        while self._running:
            try:
                changed = self.reload_changed()
                if changed:
                    log.info("پلاگین‌های به‌روزرسانی‌شده: %s", ", ".join(changed))
            except Exception:  # noqa: BLE001
                log.exception("خطا در چرخهٔ نظارت")
            await asyncio.sleep(interval_s)

    def stop_watch(self) -> None:
        self._running = False
