-- Schema پایهٔ اسکلت (فاز ۱) — با Alembic در فازهای بعد جایگزین می‌شود.

CREATE TABLE IF NOT EXISTS groups (
    chat_id    INTEGER PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    username   TEXT NOT NULL DEFAULT '',
    lang       TEXT NOT NULL DEFAULT 'fa',
    settings   TEXT NOT NULL DEFAULT '{}',
    approved   INTEGER NOT NULL DEFAULT 1,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    lang       TEXT NOT NULL DEFAULT 'fa',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS group_roles (
    chat_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('mod', 'admin', 'co_owner', 'owner')),
    title      TEXT NOT NULL DEFAULT '',
    by_user    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_group_roles_user ON group_roles (user_id);
