"""
سرویس دسترسی — محاسبهٔ «سطح مؤثر» یک کاربر در یک گروه.

منابع سطح (به ترتیب اولویت):
    1. مالک ربات / سودوها (Config)          → SUDO
    2. نقش ذخیره‌شده در دیتابیس (co_owner…) → سطح مربوط
    3. خالق گروه (creator_provider)          → OWNER
    4. در غیر این صورت                       → USER

creator_provider یک تابع تزریقی است که chat_id می‌گیرد و آیدی خالق را برمی‌گرداند
(در فاز ۲ از تلگرام خوانده می‌شود؛ الان می‌تواند None باشد).
"""

from __future__ import annotations

from typing import Callable

from bot.domain.roles import AccessLevel, level_from_db_role
from bot.repositories.base import RoleRepo

CreatorProvider = Callable[[int], int | None]


class AccessService:
    def __init__(
        self,
        role_repo: RoleRepo,
        *,
        owner_id: int,
        sudo_ids: tuple[int, ...] = (),
        creator_provider: CreatorProvider | None = None,
    ) -> None:
        self._roles = role_repo
        self._owner_id = owner_id
        self._sudo_ids = frozenset(sudo_ids)
        self._creator = creator_provider

    def is_bot_owner(self, user_id: int) -> bool:
        return user_id == self._owner_id

    def level(self, chat_id: int, user_id: int) -> AccessLevel:
        """سطح مؤثر کاربر در گروه."""
        if self.is_bot_owner(user_id) or user_id in self._sudo_ids:
            return AccessLevel.SUDO

        if self._creator is not None:
            creator = self._creator(chat_id)
            if creator is not None and creator == user_id:
                return AccessLevel.OWNER

        role = self._roles.get_role(chat_id, user_id)
        return level_from_db_role(role)

    def can(self, chat_id: int, user_id: int, required: AccessLevel) -> bool:
        return self.level(chat_id, user_id) >= required

    def require(self, chat_id: int, user_id: int, required: AccessLevel) -> AccessLevel | None:
        """
        خروجی: سطح واقعی اگر مجاز است، وگرنه None
        (برای پیام «⛔ دسترسی ندارید» در لایهٔ نمایش).
        """
        actual = self.level(chat_id, user_id)
        if actual < required:
            return None
        return actual
