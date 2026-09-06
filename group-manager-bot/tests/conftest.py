"""فیکسچرهای مشترک — دیتابیس، ریپازیتوری، مترجم و کارخانهٔ کامل (host+dispatcher)."""

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
from bot.repositories.sqlite_repo import (
    SqliteActionRepo,
    SqliteGroupRepo,
    SqliteRoleRepo,
    SqliteUserRepo,
    SqliteWarnRepo,
)
from bot.services.access_service import AccessService

REAL_PLUGINS = Path(__file__).resolve().parent.parent / "plugins"


def _copy_real_plugins(dst: Path) -> None:
    """کپی پلاگین‌های نمونه در پوشهٔ موقت (برای تست بدون دست‌زدن به سورس)."""
    dst.mkdir(parents=True, exist_ok=True)
    for folder in REAL_PLUGINS.iterdir():
        if folder.is_dir() and (folder / "plugin.py").is_file():
            shutil.copytree(folder, dst / folder.name, dirs_exist_ok=True)


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


@pytest.fixture()
def repos(db):
    return (
        SqliteGroupRepo(db),
        SqliteRoleRepo(db),
        SqliteUserRepo(db),
    )


@pytest.fixture()
def translator():
    return Translator()


@pytest.fixture()
def e2e(tmp_path):
    """هستهٔ کامل: DB → repos(+warns/actions) → host(پلاگین‌های واقعی) → dispatcher."""
    db = Database(tmp_path / "e2e.db")
    db.init_schema()
    groups, users, roles = SqliteGroupRepo(db), SqliteUserRepo(db), SqliteRoleRepo(db)
    warns, actions = SqliteWarnRepo(db), SqliteActionRepo(db)
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
        warns=warns,
        actions=actions,
    )
    host.load_all()

    from bot.dispatcher import Dispatcher

    d = Dispatcher(
        host.registry,
        access,
        Translator(),
        default_lang="fa",
        plugin_enabled=host.is_plugin_enabled,
    )
    return host, d, groups, roles, plugins_dir
