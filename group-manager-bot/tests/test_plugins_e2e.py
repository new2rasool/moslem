"""تست سرتاسری با پلاگین‌های واقعی پوشهٔ plugins/ (بدون تلگرام).

اثبات: پلاگین‌ها در پوشهٔ plugins خودکار کشف می‌شوند، فرمان‌هایشان از مسیریاب
هسته اجرا می‌شود و رویدادها بینشان پخش می‌شود — بدون هیچ تغییری در هسته.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bot.cache.cache import MemoryCache
from bot.config import Config
from bot.db.engine import Database
from bot.i18n.loader import Translator
from bot.plugin_host import PluginHost
from bot.registry import Registry
from bot.repositories.sqlite_repo import SqliteGroupRepo, SqliteRoleRepo, SqliteUserRepo
from bot.services.access_service import AccessService

REAL_PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


def _copy_real_plugins(dst: Path) -> None:
    """کپی پلاگین‌های نمونه در پوشهٔ موقت (برای تست بدون دست‌زدن به سورس)."""
    dst.mkdir(parents=True, exist_ok=True)
    for folder in REAL_PLUGINS.iterdir():
        if folder.is_dir() and (folder / "plugin.py").is_file():
            shutil.copytree(folder, dst / folder.name, dirs_exist_ok=True)


@pytest.fixture()
def e2e(tmp_path):
    db = Database(tmp_path / "e2e.db")
    db.init_schema()
    groups, users, roles = SqliteGroupRepo(db), SqliteUserRepo(db), SqliteRoleRepo(db)
    cfg = Config(owner_id=1, sudo_ids=(2,), default_lang="fa")
    access = AccessService(roles, owner_id=1, sudo_ids=(2,))
    plugins_dir = tmp_path / "plugins"
    _copy_real_plugins(plugins_dir)
    host = PluginHost(
        cfg=cfg,
        plugins_dir=plugins_dir,
        translator=Translator(),
        registry=Registry(),
        access=access,
        cache=MemoryCache(),
        groups=groups,
        users=users,
        roles=roles,
    )
    host.load_all()

    from bot.dispatcher import Dispatcher

    d = Dispatcher(host.registry, access, Translator(), default_lang="fa")
    return host, d, groups, roles, plugins_dir


def test_all_sample_plugins_auto_discovered(e2e):
    host, *_ = e2e
    enabled = host.enabled_names()
    for name in ("ping", "whoami", "greeter", "admin_utils"):
        assert name in enabled


@pytest.mark.asyncio
async def test_ping_command_runs_from_plugin(e2e):
    _, d, *_ = e2e
    out = await d.try_dispatch_command("/ping", chat_id=None, user_id=1, is_private=True)
    assert out and "پونگ" in out[0]  # ترجمهٔ فارسی خودِ پلاگین ping


@pytest.mark.asyncio
async def test_whoami_shows_access_level(e2e):
    _, d, _, roles, _ = e2e
    roles.set_role(-1001, 10, "mod", by_user=1)
    out = await d.try_dispatch_command("من", chat_id=-1001, user_id=10, lang="fa")
    assert out and "مدیر میانی" in out[0]


@pytest.mark.asyncio
async def test_admin_command_denied_for_user(e2e):
    _, d, _, _, _ = e2e
    out = await d.try_dispatch_command("/duration 1h", chat_id=-1001, user_id=99, lang="fa")
    assert out and "دسترسی ندارید" in out[0]


@pytest.mark.asyncio
async def test_duration_parses_for_mod(e2e):
    _, d, _, roles, _ = e2e
    roles.set_role(-1001, 11, "mod", by_user=1)
    out = await d.try_dispatch_command("/duration 1d6h30m", chat_id=-1001, user_id=11, lang="fa")
    assert out and "109800" in out[0]


@pytest.mark.asyncio
async def test_greeter_event_fires_on_member_joined(e2e):
    _, d, _, _, _ = e2e
    out = await d.dispatch_event(
        "member_joined",
        chat_id=-1001,
        lang="fa",
        user_id=777,
        user_name="مریم",
        data={"member_name": "مریم", "member_username": "", "chat_title": "انجمن"},
    )
    assert out and "مریم" in out[0] and "خوش آمدی" in out[0]


@pytest.mark.asyncio
async def test_help_lists_all_plugin_commands(e2e):
    _, d, *_ = e2e
    out = await d.try_dispatch_command("/help", chat_id=None, user_id=1, is_private=True, lang="fa")
    text = "\n".join(out or [])
    for token in ("/ping", "/whoami", "/duration", "/id"):
        assert token in text
    assert "4 پلاگین" in text or "پلاگین" in text


@pytest.mark.asyncio
async def test_duplicate_command_conflict_reported(e2e):
    """افزودن پلاگین جدید با فرمان تکراری → خودکار کنار گذاشته می‌شود بدون خرابی."""
    host, d, _, _, plugins_dir = e2e
    bad = plugins_dir / "clash"
    bad.mkdir()
    (bad / "plugin.py").write_text(
        "def register(api):\n"
        "    async def p(ctx): ctx.respond('x')\n"
        "    api.register_command('ping', p)\n",
        encoding="utf-8",
    )
    touched = host.reload_changed()  # پلاگین تازه در همان پوشه شناسایی شد
    assert "clash" in touched
    assert "clash" in host.failed_names()  # تداخل با ping پلاگین موجود → رد شد
    # فرمان ping اصلی (از پلاگین نمونه) سالم است
    out = await d.try_dispatch_command("/ping", chat_id=None, user_id=1, is_private=True)
    assert out and "پونگ" in out[0]


@pytest.mark.asyncio
async def test_hot_update_changes_behavior_without_core_change(e2e):
    """ویرایش فایل پلاگین → رفتار جدید، بدون تغییر هسته یا ری‌استارت."""
    host, d, _, _, plugins_dir = e2e
    ping_file = plugins_dir / "ping" / "plugin.py"
    code = ping_file.read_text(encoding="utf-8")
    code = code.replace('ctx.respond(api.tr(ctx.lang, "pong", ms=ms, plugins=n))',
                        'ctx.respond("HOT-RELOADED")')
    ping_file.write_text(code, encoding="utf-8")

    touched = host.reload_changed()
    assert "ping" in touched
    out = await d.try_dispatch_command("/ping", chat_id=None, user_id=1, is_private=True)
    assert out == ["HOT-RELOADED"]  # هسته عوض نشد؛ پلاگین پاسخش را عوض کرد
