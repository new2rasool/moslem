"""تست‌های PluginHost — کشف خودکار، بارگذاری، ری‌لودِ بدون تغییر هسته و انزوا."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.cache.cache import MemoryCache
from bot.config import Config
from bot.domain.roles import AccessLevel
from bot.i18n.loader import Translator
from bot.plugin_host import PluginHost
from bot.registry import CommandConflictError, Registry
from bot.services.access_service import AccessService

PING_PLUGIN_V1 = '''\
PLUGIN_VERSION = "1.0.0"
def register(api):
    async def ping(ctx):
        ctx.respond("pong-v1")
    api.register_command("ping", ping, aliases=("ping", "پینگ"))
'''

PING_PLUGIN_V2 = '''\
PLUGIN_VERSION = "2.0.0"
def register(api):
    async def ping(ctx):
        ctx.respond("pong-v2")
    api.register_command("ping", ping, aliases=("ping", "پینگ"))
'''

BAD_PLUGIN = '''\
def register(api):
    raise RuntimeError("boom")
'''

GREETER_PLUGIN = '''\
from bot.registry import EVENT_MEMBER_JOINED
def register(api):
    async def on_join(ctx):
        ctx.respond("welcome " + str(ctx.data.get("member_name", "")))
    api.register_event(EVENT_MEMBER_JOINED, on_join)
'''


@pytest.fixture()
def make_host(repos, tmp_path):
    cfg = Config(owner_id=1, sudo_ids=(2,), default_lang="fa")
    groups, users, roles = repos
    access = AccessService(roles, owner_id=1, sudo_ids=(2,))

    def factory(plugins_dir: Path) -> PluginHost:
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
        return host

    return factory


def _write(tmp_path, name: str, code: str) -> Path:
    d = tmp_path / "plugins" / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "plugin.py"
    f.write_text(code, encoding="utf-8")
    return f


# ── کشف و بارگذاری خودکار ──────────────────────────────────────────
def test_autoload_single_file_plugin(tmp_path, make_host):
    d = tmp_path / "plugins"
    d.mkdir()
    (d / "one.py").write_text(PING_PLUGIN_V1, encoding="utf-8")
    host = make_host(d)
    assert "one" in host.enabled_names()
    assert host.records["one"].version == "1.0.0"
    assert host.records["one"].commands == 1


def test_autoload_folder_plugin(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "ping", PING_PLUGIN_V1)
    host = make_host(d)
    assert "ping" in host.enabled_names()


def test_core_system_commands_always_present(make_host, tmp_path):
    d = tmp_path / "empty_plugins"
    d.mkdir()
    host = make_host(d)
    registry = host.registry
    # فرمان‌های میزبان هسته (help/start/...) بدون هیچ پلاگینی موجودند
    assert registry.command("help") is not None
    assert registry.command("start") is not None


def test_broken_plugin_does_not_break_host(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "good", PING_PLUGIN_V1)
    _write(tmp_path, "bad", BAD_PLUGIN)
    host = make_host(d)
    assert "good" in host.enabled_names()
    assert "bad" in host.failed_names()
    assert "boom" in host.records["bad"].error
    # فرمان پلاگین سالم هنوز ثبت است
    assert host.registry.command("ping") is not None


def test_plugin_name_conflict_fails_second(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "p1", PING_PLUGIN_V1)
    _write(tmp_path, "p2", PING_PLUGIN_V1)
    host = make_host(d)
    # هر دو پلاگین فرمان «ping» را ثبت می‌کنند → دومی ناموفق (بدون شکستن اولی)
    assert "p1" in host.enabled_names()
    assert "p2" in host.failed_names()
    assert "قبلاً" in host.records["p2"].error or "تداخل" in host.records["p2"].error
    assert host.registry.command("ping") is not None  # از پلاگین اول باقی است


# ── ری‌لود پویا بدون تغییر هسته ─────────────────────────────────────
def test_add_new_plugin_then_reload_changed(tmp_path, make_host):
    d = tmp_path / "plugins"
    d.mkdir()
    host = make_host(d)
    assert host.enabled_names() == []
    assert host.registry.command("ping") is None

    # پلاگین جدید اضافه شد — بدون restart و بدون تغییر هسته
    _write(tmp_path, "ping", PING_PLUGIN_V1)
    touched = host.reload_changed()
    assert "ping" in touched
    assert host.registry.command("ping") is not None


def test_update_plugin_code_without_core_change(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "ping", PING_PLUGIN_V1)
    host = make_host(d)
    assert host.records["ping"].version == "1.0.0"

    # فایل پلاگین ویرایش شد (v2) — هات‌ری‌لود
    _write(tmp_path, "ping", PING_PLUGIN_V2)
    touched = host.reload_changed()
    assert "ping" in touched
    assert host.records["ping"].version == "2.0.0"
    assert len(host.enabled_names()) == 1  # بدون تکرار/ردپای کهنه


def test_remove_plugin_file_then_reload(tmp_path, make_host):
    d = tmp_path / "plugins"
    f = _write(tmp_path, "ping", PING_PLUGIN_V1)
    host = make_host(d)
    assert "ping" in host.enabled_names()

    f.unlink()
    touched = host.reload_changed()
    assert "ping" in touched
    assert host.enabled_names() == []
    assert host.registry.command("ping") is None


def test_manual_unload_and_load(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "ping", PING_PLUGIN_V1)
    host = make_host(d)
    assert host.unload("ping") is True
    assert host.registry.command("ping") is None
    assert host.load("ping") is True
    assert host.registry.command("ping") is not None


def test_reload_one_plugin_keeps_others(tmp_path, make_host):
    d = tmp_path / "plugins"
    _write(tmp_path, "ping", PING_PLUGIN_V1)
    _write(tmp_path, "greeter", GREETER_PLUGIN)
    host = make_host(d)
    host.reload("ping")
    assert "ping" in host.enabled_names()
    assert "greeter" in host.enabled_names()
    assert host.registry.events("member_joined")  # رویداد greeter باقی است


def test_discover_ignores_irrelevant_files(tmp_path, make_host):
    d = tmp_path / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    (d / "readme.txt").write_text("note", encoding="utf-8")
    (d / "__init__.py").write_text("", encoding="utf-8")
    (d / "sub").mkdir()
    (d / "sub" / "no_plugin.py").write_text("x=1", encoding="utf-8")  # پوشه بدون plugin.py
    host = make_host(d)
    assert host.enabled_names() == []  # هیچ‌کدام پلاگین نیستند
