"""تست‌های سطوح دسترسی و قواعد تنبیه — domain/roles.py + services/access_service.py"""

import pytest

from bot.domain.roles import (
    AccessLevel,
    MIN_COMMAND_LEVEL,
    db_role_for_level,
    can,
    can_punish,
    level_from_db_role,
)
from bot.repositories.base import Group
from bot.services.access_service import AccessService


# ── نگاشت نقش ↔ سطح ────────────────────────────────────────────────
def test_db_role_mapping():
    assert level_from_db_role("mod") is AccessLevel.MOD
    assert level_from_db_role("admin") is AccessLevel.ADMIN
    assert level_from_db_role("co_owner") is AccessLevel.CO_OWNER
    assert level_from_db_role("owner") is AccessLevel.OWNER
    assert level_from_db_role(None) is AccessLevel.USER
    assert level_from_db_role("weird") is AccessLevel.USER


def test_db_role_roundtrip():
    for lvl in (AccessLevel.MOD, AccessLevel.ADMIN, AccessLevel.CO_OWNER, AccessLevel.OWNER):
        assert level_from_db_role(db_role_for_level(lvl)) is lvl


def test_db_role_invalid_levels():
    with pytest.raises(ValueError):
        db_role_for_level(AccessLevel.USER)
    with pytest.raises(ValueError):
        db_role_for_level(AccessLevel.SUDO)


# ── can ─────────────────────────────────────────────────────────────
def test_can():
    assert can(AccessLevel.ADMIN, AccessLevel.ADMIN)
    assert can(AccessLevel.SUDO, AccessLevel.OWNER)
    assert not can(AccessLevel.MOD, AccessLevel.ADMIN)
    assert not can(AccessLevel.USER, AccessLevel.MOD)


# ── قواعد تنبیه ─────────────────────────────────────────────────────
def test_punish_rank_matrix():
    # بالاتر می‌تواند پایین‌تر را تنبیه کند
    ok, _ = can_punish(AccessLevel.ADMIN, AccessLevel.MOD)
    assert ok
    ok, _ = can_punish(AccessLevel.SUDO, AccessLevel.OWNER)
    assert ok
    # هم‌سطح نه، پایین‌تر به بالاتر نه
    ok, reason = can_punish(AccessLevel.ADMIN, AccessLevel.ADMIN)
    assert not ok and reason == "target_not_lower"
    ok, reason = can_punish(AccessLevel.MOD, AccessLevel.ADMIN)
    assert not ok and reason == "target_not_lower"


def test_bot_owner_immune():
    ok, reason = can_punish(
        AccessLevel.SUDO, AccessLevel.OWNER, actor_is_bot_owner=False, target_is_bot_owner=True
    )
    assert not ok and reason == "bot_owner_immune"
    # مالک ربات توسط خودش قابل تنبیه است (از نظر قواعد)
    ok, _ = can_punish(
        AccessLevel.SUDO, AccessLevel.OWNER, actor_is_bot_owner=True, target_is_bot_owner=True
    )
    assert ok


# ── نمونه‌فرمان‌ها ──────────────────────────────────────────────────
def test_min_command_level_map():
    assert MIN_COMMAND_LEVEL["ban"] is AccessLevel.ADMIN
    assert MIN_COMMAND_LEVEL["warn"] is AccessLevel.MOD
    assert MIN_COMMAND_LEVEL["kickme"] is AccessLevel.USER
    assert MIN_COMMAND_LEVEL["gban"] is AccessLevel.SUDO
    assert MIN_COMMAND_LEVEL["rules"] is AccessLevel.USER


# ── سرویس دسترسی (یکپارچه با SQLite) ───────────────────────────────
OWNER = 1
SUDOS = (2,)
CREATOR = 555
CHAT = -1001


@pytest.fixture()
def access(repos):
    _, roles, _ = repos
    roles.set_role(CHAT, 10, "mod", by_user=OWNER)
    roles.set_role(CHAT, 20, "admin", by_user=OWNER)
    roles.set_role(CHAT, 30, "co_owner", by_user=OWNER)
    return AccessService(
        roles,
        owner_id=OWNER,
        sudo_ids=SUDOS,
        creator_provider=lambda _chat: CREATOR,
    )


def test_access_levels(access):
    assert access.level(CHAT, OWNER) is AccessLevel.SUDO  # مالک ربات
    assert access.level(CHAT, 2) is AccessLevel.SUDO  # سودو
    assert access.level(CHAT, CREATOR) is AccessLevel.OWNER  # خالق گروه
    assert access.level(CHAT, 30) is AccessLevel.CO_OWNER
    assert access.level(CHAT, 20) is AccessLevel.ADMIN
    assert access.level(CHAT, 10) is AccessLevel.MOD
    assert access.level(CHAT, 999) is AccessLevel.USER


def test_access_can_and_require(access):
    assert access.can(CHAT, 20, AccessLevel.ADMIN)
    assert not access.can(CHAT, 10, AccessLevel.ADMIN)
    assert access.require(CHAT, OWNER, AccessLevel.SUDO) is AccessLevel.SUDO
    assert access.require(CHAT, 10, AccessLevel.ADMIN) is None


def test_access_other_chat_ignores_roles(access):
    # نقش‌ها گروه‌محورند: در گروه دیگر همان کاربر عادی است
    assert access.level(-1002, 20) is AccessLevel.USER


def test_access_creator_missing_uses_db_owner_role(repos, db):
    _, roles, _ = repos
    groups, _, _ = repos  # گروه هم برای صحنه لازم نیست؛ فقط نقش owner
    roles.set_role(CHAT, CREATOR, "owner", by_user=OWNER)
    svc = AccessService(roles, owner_id=OWNER, creator_provider=None)
    assert svc.level(CHAT, CREATOR) is AccessLevel.OWNER
