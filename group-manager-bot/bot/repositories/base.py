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
