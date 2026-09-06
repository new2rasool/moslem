"""
پیکربندی — بارگذاری از متغیرهای محیط بدون وابستگی خارجی.

اصل: پیکربندی در یک نقطهٔ واحد (این ماژول) خوانده می‌شود و هیچ‌کس دیگری
مستقیماً به `os.environ` دست نمی‌زند.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    """خطای معتبرنبودن پیکربندی."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} باید عدد صحیح باشد، دریافت شد: {raw!r}") from exc


def _env_int_list(name: str) -> tuple[int, ...]:
    raw = _env(name)
    if not raw:
        return ()
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError as exc:
            raise ConfigError(f"{name} باید فهرست اعداد با کاما باشد: {raw!r}") from exc
    return tuple(out)


@dataclass(frozen=True)
class Config:
    """پیکربندی نرمال‌شده و اعتبارسنجی‌شده."""

    bot_token: str = ""
    owner_id: int = 0
    sudo_ids: tuple[int, ...] = ()
    database_url: str = "sqlite:///data/group-manager.db"
    redis_url: str = ""
    default_lang: str = "fa"
    log_level: str = "INFO"
    plugins_dir: str = ""
    groups_cache_ttl_s: int = 30
    admins_cache_ttl_s: int = 60

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        """ساخت پیکربندی از environ (برای تست می‌توان env ساختگی داد)."""
        if env is None:
            env = os.environ
        old = dict(os.environ)
        try:
            if env is not os.environ:
                os.environ.clear()
                os.environ.update(env)
            lang = _env("GMB_DEFAULT_LANG", "fa").lower()
            if lang not in ("fa", "en"):
                raise ConfigError("GMB_DEFAULT_LANG باید fa یا en باشد")
            log_level = _env("GMB_LOG_LEVEL", "INFO").upper()
            if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                raise ConfigError("GMB_LOG_LEVEL نامعتبر است")
            cfg = cls(
                bot_token=_env("BOT_TOKEN"),
                owner_id=_env_int("OWNER_ID", 0),
                sudo_ids=_env_int_list("SUDO_IDS"),
                database_url=_env("GMB_DB_URL", "sqlite:///data/group-manager.db"),
                redis_url=_env("GMB_REDIS_URL"),
                default_lang=lang,
                log_level=log_level,
                plugins_dir=_env("GMB_PLUGINS_DIR"),
                groups_cache_ttl_s=_env_int("GMB_GROUPS_CACHE_TTL_S", 30),
                admins_cache_ttl_s=_env_int("GMB_ADMINS_CACHE_TTL_S", 60),
            )
            return cfg
        finally:
            if env is not os.environ:
                os.environ.clear()
                os.environ.update(old)

    def validate(self, require_token: bool = False) -> None:
        if self.owner_id <= 0:
            raise ConfigError("OWNER_ID الزامی است (آیدی عددی مالک ربات)")
        if require_token and not self.bot_token:
            raise ConfigError("BOT_TOKEN الزامی است (از BotFather بگیرید)")

    @property
    def sqlite_path(self) -> Path | None:
        """اگر URL به‌صورت sqlite باشد مسیر فایل را برمی‌گرداند."""
        if not self.database_url.startswith("sqlite:///"):
            return None
        raw = self.database_url[len("sqlite:///") :]
        if not raw or raw == ":memory:":
            return None
        return Path(raw)

    def is_sudo(self, user_id: int) -> bool:
        return user_id == self.owner_id or user_id in self.sudo_ids


# نمونهٔ سراسری — پس از from_env مقداردهی می‌شود
settings: Config | None = None


def load() -> Config:
    global settings
    if settings is None:
        settings = Config.from_env()
    return settings
