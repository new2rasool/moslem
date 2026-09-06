"""تست سلامت CLI — اجرای --check با محیط حداقلی (شرط خروج فاز ۱)."""

from bot.config import Config
from bot.logging_setup import setup_logging

# لوکال‌ها را از مسیر بسته بار می‌کنیم؛ لاگ را خاموش می‌کنیم
setup_logging("WARNING")


def test_config_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("OWNER_ID", "123")
    monkeypatch.setenv("GMB_DB_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    cfg = Config.from_env()
    assert cfg.owner_id == 123
    assert cfg.is_sudo(123)
    assert not cfg.is_sudo(456)
    cfg.validate()


def test_config_missing_owner_fails(monkeypatch):
    monkeypatch.delenv("OWNER_ID", raising=False)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    cfg = Config.from_env()
    import pytest

    with pytest.raises(Exception):
        cfg.validate(require_token=True)


def test_cli_check_exit_zero(monkeypatch, tmp_path, capsys):
    """بررسی سلامت هستهٔ پلاگین‌محور باید با کد صفر تمام شود."""
    monkeypatch.setenv("OWNER_ID", "123")
    monkeypatch.setenv("SUDO_IDS", "2,3")
    monkeypatch.setenv("GMB_DB_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("GMB_PLUGINS_DIR", str(tmp_path / "empty_plugins"))

    from bot.main import main

    code = main(["--check"])
    out = capsys.readouterr().out
    assert code == 0
    assert "سالم است" in out
