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

-- ── سیستم هشدار (هر ردیف = یک هشدار) ────────────────────────────────
CREATE TABLE IF NOT EXISTS warns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    reason     TEXT NOT NULL DEFAULT '',
    by_user    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_warns_chat_user ON warns (chat_id, user_id);

-- ── دفتر حسابرسی اکشن‌ها (audit ledger) ─────────────────────────────
CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    action      TEXT NOT NULL,
    target_user INTEGER NOT NULL,
    by_user     INTEGER NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    duration_s  INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_actions_chat ON actions (chat_id);
CREATE INDEX IF NOT EXISTS idx_actions_created ON actions (created_at);
