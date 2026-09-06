"""
نقطهٔ ورود ربات — بوت‌استرپ هسته + بارگذاری خودکار پلاگین‌ها.

    python -m bot.main --check          بررسی سلامت (بدون تلگرام/توکن)
    python -m bot.main --run            اجرای واقعی (نیازمند Pyrogram + BOT_TOKEN)
    python -m bot.main --run --watch    + هات‌ری‌لود خودکار پوشهٔ plugins
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from bot import __version__
from bot.cache.cache import MemoryCache
from bot.config import Config, ConfigError, load
from bot.db.engine import Database
from bot.dispatcher import Dispatcher
from bot.i18n.loader import Translator
from bot.logging_setup import get_logger, setup_logging
from bot.plugin_host import PluginHost
from bot.registry import Registry
from bot.repositories.base import Group
from bot.repositories.sqlite_repo import (
    SqliteActionRepo,
    SqliteGroupRepo,
    SqliteRoleRepo,
    SqliteUserRepo,
    SqliteWarnRepo,
)
from bot.services.access_service import AccessService

log = get_logger("main")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLUGINS_DIR = PROJECT_ROOT / "plugins"


def _resolve_plugins_dir(cfg: Config) -> Path:
    if cfg.plugins_dir:
        return Path(cfg.plugins_dir).resolve()
    return DEFAULT_PLUGINS_DIR


def build_host(cfg: Config) -> tuple[PluginHost, Dispatcher]:
    """ساخت کامل هسته: DB → ریپازیتوری → دسترسی → رجیستری → دیسپچر → هاست."""
    path = cfg.sqlite_path
    if path is None:
        raise ConfigError("در این نسخه فقط sqlite پشتیبانی می‌شود (GMB_DB_URL)")
    db = Database(path)
    db.init_schema()

    groups = SqliteGroupRepo(db)
    users = SqliteUserRepo(db)
    roles = SqliteRoleRepo(db)
    warns = SqliteWarnRepo(db)
    actions = SqliteActionRepo(db)
    access = AccessService(roles, owner_id=cfg.owner_id, sudo_ids=cfg.sudo_ids)
    translator = Translator()
    registry = Registry()
    cache: MemoryCache = MemoryCache()
    host = PluginHost(
        cfg=cfg,
        plugins_dir=_resolve_plugins_dir(cfg),
        translator=translator,
        registry=registry,
        access=access,
        cache=cache,
        groups=groups,
        users=users,
        roles=roles,
        warns=warns,
        actions=actions,
    )
    host.load_all()
    dispatcher = Dispatcher(
        registry,
        access,
        translator,
        default_lang=cfg.default_lang,
        plugin_enabled=host.is_plugin_enabled,
    )
    return host, dispatcher


# ─────────────────────────────────────────────────────────────────────
def cmd_check(cfg: Config) -> int:
    """بررسی سلامت اسکلت پلاگین‌محور (شرط خروج فاز ۱)."""
    setup_logging(cfg.log_level)
    print(f"\n🧩 group-manager-bot v{__version__} — بررسی هستهٔ پلاگین‌محور\n")
    failed = False

    try:
        cfg.validate(require_token=False)
        print(f"  ✅ پیکربندی: مالک={cfg.owner_id} | سودو={list(cfg.sudo_ids) or '—'}")
    except ConfigError as exc:
        print(f"  ❌ پیکربندی: {exc}")
        failed = True

    try:
        host, dispatcher = build_host(cfg)
        records = host.records
        if records:
            for name in sorted(records):
                rec = records[name]
                mark = "✅" if rec.enabled else "❌"
                print(
                    f"  {mark} پلاگین {name} v{rec.version} | "
                    f"{rec.commands} فرمان · {rec.events} رویداد"
                    + (f" | ⚠️ {rec.error}" if rec.failed else "")
                )
        else:
            print("  ⚠️ هیچ پلاگینی در پوشهٔ plugins یافت نشد")
        total_cmds = len(dispatcher.registry.commands())
        print(f"  ✅ رجیستری: {total_cmds} فرمان کل | رویدادها: "
              f"{dispatcher.registry.event_kinds()}")

        # شبیه‌سازی سراسری: /help برای مالک باید فهرست پویا بدهد
        async def _smoke() -> list[str] | None:
            return await dispatcher.try_dispatch_command(
                "/help", chat_id=None, user_id=cfg.owner_id, is_private=True, lang=cfg.default_lang
            )

        replies = asyncio.run(_smoke())
        if replies:
            sample = replies[0]
            print("  ✅ شبیه‌سازی /help: پاسخ با فهرست پویای پلاگین‌ها آماده شد")
            if cfg.default_lang == "fa":
                print(sample.splitlines()[0])
        else:
            print("  ❌ /help پاسخی نداد")
            failed = True
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ بارگذاری: {exc}")
        failed = True

    print("\n  نتیجه: " + ("❌ ناقص — موارد بالا را برطرف کنید."
                           if failed else "✅ هستهٔ پلاگین‌محور سالم است (پلاگین‌ها خودکار بارگذاری شدند)."))
    return 1 if failed else 0


# ─────────────────────────────────────────────────────────────────────
def cmd_run(cfg: Config, watch: bool = False) -> int:
    """اجرای واقعی — آداپتور تلگرام (Pyrogram) + دیسپچر پلاگین‌ها."""
    setup_logging(cfg.log_level)
    try:
        cfg.validate(require_token=True)
    except ConfigError as exc:
        print(f"❌ {exc}")
        return 2

    try:
        from pyrogram import Client, enums  # noqa: PLC0415
    except ImportError:
        print("❌ Pyrogram نصب نیست. اجرا کنید:  pip install -e '.[run]'")
        return 2

    host, dispatcher = build_host(cfg)
    print(f"✅ {len(host.enabled_names())} پلاگین بارگذاری شد: "
          + ", ".join(host.enabled_names()))

    workdir = str(PROJECT_ROOT / "data")
    app = Client("group_manager_bot", bot_token=cfg.bot_token, workdir=workdir)

    async def _lang(chat_id, user_id, is_private) -> str:
        if is_private and user_id:
            u = host.users.get(user_id)
            if u:
                return u.lang
        elif chat_id:
            g = host.groups.get(chat_id)
            if g:
                return g.lang
        return cfg.default_lang

    @app.on_message()
    async def on_message(client, message):  # noqa: ANN001
        try:
            chat = message.chat
            is_private = bool(chat and chat.type == enums.ChatType.PRIVATE)
            chat_id = None if (chat is None or is_private) else chat.id
            user = message.from_user
            if user is None:
                return
            # رویدادهای عضو
            if message.new_chat_members:
                for member in message.new_chat_members:
                    await dispatcher.dispatch_event(
                        "member_joined",
                        chat_id=chat_id,
                        lang=await _lang(chat_id, None, False),
                        user_id=member.id,
                        user_name=(member.first_name or "") + (member.last_name or ""),
                        user_username=member.username or "",
                        data={"member_id": member.id,
                              "member_name": (member.first_name or ""),
                              "member_username": member.username or "",
                              "chat_title": chat.title if chat else ""},
                    )
            # فرمان متنی
            if message.text:
                sends = await dispatcher.try_dispatch_command(
                    message.text,
                    chat_id=chat_id,
                    user_id=user.id,
                    is_private=is_private,
                    lang=await _lang(chat_id, user.id, is_private),
                    sender_name=(user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                    sender_username=user.username or "",
                )
                if sends:
                    for text in sends:
                        await message.reply(text)
        except Exception:  # noqa: BLE001
            log.exception("خطا در پردازش پیام")

    watcher = None
    if watch:
        loop = asyncio.get_event_loop()
        watcher = loop.create_task(host.watch_loop(1.0))
        print("👀 نظارت بر پوشهٔ پلاگین‌ها فعال است (هات‌ری‌لود)")

    # حلقهٔ پس‌زمینه برای on_tick پلاگین‌ها (انقضای کپچا، رهاسازی راید و…)
    loop = asyncio.get_event_loop()
    loop.create_task(host.start_background(2.0))

    log.info("ربات در حال اجراست (هستهٔ پلاگین‌محور).")
    try:
        app.run()
    finally:
        if watcher:
            watcher.cancel()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="group-manager-bot", description="ربات مدیریت گروه پلاگین‌محور")
    parser.add_argument("--run", action="store_true", help="اجرای واقعی ربات")
    parser.add_argument("--watch", action="store_true", help="هات‌ری‌لود خودکار پلاگین‌ها (با --run)")
    parser.add_argument("--check", action="store_true", help="بررسی سلامت هسته و پلاگین‌ها")
    args = parser.parse_args(argv)

    try:
        cfg = load()
    except ConfigError as exc:
        print(f"❌ خطای پیکربندی: {exc}")
        return 2

    if args.run:
        return cmd_run(cfg, watch=args.watch)
    return cmd_check(cfg)  # پیش‌فرض = --check


if __name__ == "__main__":
    sys.exit(main())
