"""
نقش‌ها و سطوح دسترسی (دامنهٔ خالص).

سلسله‌مراتب (از پایین به بالا):
    USER → MOD → ADMIN → CO_OWNER → OWNER(گروه) → SUDO(مالک ربات)

همهٔ قواعد «چه کسی می‌تواند چه کند» این‌جا و فقط این‌جا تعریف می‌شود.
"""

from __future__ import annotations

from enum import IntEnum


class AccessLevel(IntEnum):
    """سطح دسترسی مؤثر یک کاربر در یک گروه."""

    USER = 0
    MOD = 1        # مدیر میانی
    ADMIN = 2      # ادمین ربات
    CO_OWNER = 3   # معاون مالک گروه
    OWNER = 4      # مالک گروه (خالق)
    SUDO = 5       # مالک ربات / سودو


# ── نگاشت نقش ذخیره‌شده در دیتابیس ↔ سطح ────────────────────────────
DB_ROLE_TO_LEVEL: dict[str, AccessLevel] = {
    "mod": AccessLevel.MOD,
    "admin": AccessLevel.ADMIN,
    "co_owner": AccessLevel.CO_OWNER,
    "owner": AccessLevel.OWNER,
}


def level_from_db_role(role: str | None) -> AccessLevel:
    if role is None:
        return AccessLevel.USER
    return DB_ROLE_TO_LEVEL.get(role, AccessLevel.USER)


def db_role_for_level(level: AccessLevel) -> str:
    """نقشِ قابل‌ذخیره برای یک سطح (فقط نقش‌های گروهی)."""
    if level is AccessLevel.USER or level is AccessLevel.SUDO:
        raise ValueError(f"نقش دیتابیسی برای {level.name} وجود ندارد")
    for role, lvl in DB_ROLE_TO_LEVEL.items():
        if lvl is level:
            return role
    raise ValueError(f"نقش دیتابیسی برای {level.name} وجود ندارد")


# ── برچسب‌های فارسی/انگلیسی برای نمایش ──────────────────────────────
LEVEL_LABELS_FA: dict[AccessLevel, str] = {
    AccessLevel.USER: "کاربر عادی",
    AccessLevel.MOD: "مدیر میانی",
    AccessLevel.ADMIN: "ادمین ربات",
    AccessLevel.CO_OWNER: "معاون مالک",
    AccessLevel.OWNER: "مالک گروه",
    AccessLevel.SUDO: "مالک ربات / سودو",
}

LEVEL_LABELS_EN: dict[AccessLevel, str] = {
    AccessLevel.USER: "User",
    AccessLevel.MOD: "Moderator",
    AccessLevel.ADMIN: "Admin",
    AccessLevel.CO_OWNER: "Co-owner",
    AccessLevel.OWNER: "Group owner",
    AccessLevel.SUDO: "Bot owner / Sudo",
}


# ── حداقل سطح لازم برای فرمان‌های نمونه (مرجع ماژول ۴.۵) ─────────────
MIN_COMMAND_LEVEL: dict[str, AccessLevel] = {
    # دسترسی کاربر عادی
    "start": AccessLevel.USER,
    "help": AccessLevel.USER,
    "rules": AccessLevel.USER,
    "report": AccessLevel.USER,
    "id": AccessLevel.USER,
    "kickme": AccessLevel.USER,
    # مدیر میانی
    "warn": AccessLevel.MOD,
    "unwarn": AccessLevel.MOD,
    "mute": AccessLevel.MOD,
    "tmute": AccessLevel.MOD,
    "kick": AccessLevel.MOD,
    "del": AccessLevel.MOD,
    "purge": AccessLevel.MOD,
    # ادمین ربات
    "ban": AccessLevel.ADMIN,
    "tban": AccessLevel.ADMIN,
    "unban": AccessLevel.ADMIN,
    "pin": AccessLevel.ADMIN,
    "setrules": AccessLevel.ADMIN,
    "antiflood": AccessLevel.ADMIN,
    "setlockmode": AccessLevel.ADMIN,
    "promote_mod": AccessLevel.ADMIN,
    # معاون/مالک گروه
    "promote": AccessLevel.CO_OWNER,
    "config": AccessLevel.CO_OWNER,
    "setlog": AccessLevel.CO_OWNER,
    "unpinall": AccessLevel.OWNER,
    # مالک ربات
    "gban": AccessLevel.SUDO,
    "broadcast": AccessLevel.SUDO,
}


# ── قواعد خالص ───────────────────────────────────────────────────────
def can(actor_level: int, required_level: int) -> bool:
    """آیا سطح actor به required می‌رسد؟"""
    return actor_level >= required_level


def can_punish(
    actor: AccessLevel,
    target: AccessLevel,
    *,
    actor_is_bot_owner: bool = False,
    target_is_bot_owner: bool = False,
) -> tuple[bool, str]:
    """
    قواعد تنبیه (بن/کیک/میوت/هشدار):

    1. مالک ربات هرگز توسط هیچ‌کس تنبیه نمی‌شود.
    2. فقط سطحِ بالاتر می‌تواند پایین‌تر را تنبیه کند (هم‌سطح نه).
    خروجی: (مجاز؟, کلید دلیل برای i18n)
    """
    if target_is_bot_owner and not actor_is_bot_owner:
        return False, "bot_owner_immune"
    if target >= actor:
        return False, "target_not_lower"
    return True, "ok"
