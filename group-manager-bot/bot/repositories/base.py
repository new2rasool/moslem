"""
اینترفیس‌های Repository — مرز «زیرساخت» از «منطق».

منطق (services) فقط به این اینترفیس‌ها وابسته است؛ تعویض SQLite→PostgreSQL
فقط با نوشتن یک پیاده‌سازی جدید انجام می‌شود (افق ۲ سند توسعه).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Group:
    chat_id: int
    title: str = ""
    username: str = ""
    lang: str = "fa"
    approved: bool = True
    active: bool = True
    settings: dict = field(default_factory=dict)


@dataclass
class User:
    user_id: int
    lang: str = "fa"


class GroupRepo(ABC):
    @abstractmethod
    def get(self, chat_id: int) -> Group | None: ...

    @abstractmethod
    def upsert(self, group: Group, merge_settings: bool = True) -> None: ...

    @abstractmethod
    def delete(self, chat_id: int) -> bool: ...


class UserRepo(ABC):
    @abstractmethod
    def get(self, user_id: int) -> User | None: ...

    @abstractmethod
    def upsert(self, user: User) -> None: ...


class RoleRepo(ABC):
    """نقش‌های «رباتی» در یک گروه (mod/admin/co_owner/owner)."""

    @abstractmethod
    def set_role(self, chat_id: int, user_id: int, role: str, by_user: int = 0, title: str = "") -> None: ...

    @abstractmethod
    def get_role(self, chat_id: int, user_id: int) -> str | None: ...

    @abstractmethod
    def delete_role(self, chat_id: int, user_id: int) -> bool: ...

    @abstractmethod
    def list_roles(self, chat_id: int) -> list[tuple[int, str, str]]:
        """فهرست (user_id, role, title) در گروه."""
        ...


class WarnRepo(ABC):
    """هشدارها — هر ردیف یک هشدار است؛ شمارش با COUNT."""

    @abstractmethod
    def add(self, chat_id: int, user_id: int, reason: str = "", by_user: int = 0) -> int:
        """افزودن یک هشدار؛ برمی‌گرداند شمار کل هشدارهای فعال کاربر."""
        ...

    @abstractmethod
    def count(self, chat_id: int, user_id: int) -> int: ...

    @abstractmethod
    def remove_last(self, chat_id: int, user_id: int) -> int:
        """حذف آخرین هشدار؛ برمی‌گرداند شمار باقی‌مانده."""
        ...

    @abstractmethod
    def reset(self, chat_id: int, user_id: int) -> None: ...

    @abstractmethod
    def last_reason(self, chat_id: int, user_id: int) -> str:
        """آخرین دلیل ثبت‌شده برای کاربر (برای نمایش)."""
        ...


class ActionRepo(ABC):
    """دفتر حسابرسی — هر اکشن (بن/سکوت/هشدار/...) یک ردیف."""

    @abstractmethod
    def add(
        self,
        chat_id: int,
        action: str,
        target_user: int,
        by_user: int,
        reason: str = "",
        duration_s: int | None = None,
    ) -> int: ...

    @abstractmethod
    def recent(self, chat_id: int, limit: int = 10) -> list[dict]:
        """آخرین اکشن‌ها (جدیدترین اول) — دیکشنری شامل id/action/target/by/reason/duration/at."""
        ...

    @abstractmethod
    def count_today(self, chat_id: int) -> int: ...
