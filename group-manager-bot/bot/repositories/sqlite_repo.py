"""پیاده‌سازی SQLite از Repositoryها (افق ۱)."""

from __future__ import annotations

import json
import sqlite3

from bot.db.engine import Database
from bot.repositories.base import Group, GroupRepo, RoleRepo, User, UserRepo


def _load_settings(raw: str) -> dict:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


class SqliteGroupRepo(GroupRepo):
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, chat_id: int) -> Group | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,)).fetchone()
        if row is None:
            return None
        return Group(
            chat_id=row["chat_id"],
            title=row["title"],
            username=row["username"],
            lang=row["lang"],
            approved=bool(row["approved"]),
            active=bool(row["active"]),
            settings=_load_settings(row["settings"]),
        )

    def upsert(self, group: Group, merge_settings: bool = True) -> None:
        existing = self.get(group.chat_id)
        settings = group.settings
        if merge_settings and existing is not None:
            settings = {**existing.settings, **group.settings}
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO groups (chat_id, title, username, lang, approved, active, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title=excluded.title,
                    username=excluded.username,
                    lang=excluded.lang,
                    approved=excluded.approved,
                    active=excluded.active,
                    settings=excluded.settings,
                    updated_at=datetime('now')
                """,
                (
                    group.chat_id,
                    group.title,
                    group.username,
                    group.lang,
                    int(group.approved),
                    int(group.active),
                    json.dumps(settings, ensure_ascii=False),
                ),
            )

    def delete(self, chat_id: int) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM groups WHERE chat_id=?", (chat_id,))
        return cur.rowcount > 0


class SqliteUserRepo(UserRepo):
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, user_id: int) -> User | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        return User(user_id=row["user_id"], lang=row["lang"])

    def upsert(self, user: User) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, lang) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang
                """,
                (user.user_id, user.lang),
            )


class SqliteRoleRepo(RoleRepo):
    def __init__(self, db: Database) -> None:
        self._db = db

    def set_role(self, chat_id: int, user_id: int, role: str, by_user: int = 0, title: str = "") -> None:
        valid = ("mod", "admin", "co_owner", "owner")
        if role not in valid:
            raise ValueError(f"نقش نامعتبر: {role!r} (مجاز: {valid})")
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO group_roles (chat_id, user_id, role, by_user, title)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    role=excluded.role, by_user=excluded.by_user, title=excluded.title,
                    created_at=datetime('now')
                """,
                (chat_id, user_id, role, by_user, title),
            )

    def get_role(self, chat_id: int, user_id: int) -> str | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT role FROM group_roles WHERE chat_id=? AND user_id=?", (chat_id, user_id)
            ).fetchone()
        return row["role"] if row else None

    def delete_role(self, chat_id: int, user_id: int) -> bool:
        with self._db.connection() as conn:
            cur = conn.execute("DELETE FROM group_roles WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        return cur.rowcount > 0

    def list_roles(self, chat_id: int) -> list[tuple[int, str, str]]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT user_id, role, title FROM group_roles WHERE chat_id=? ORDER BY created_at", (chat_id,)
            ).fetchall()
        return [(r["user_id"], r["role"], r["title"]) for r in rows]
