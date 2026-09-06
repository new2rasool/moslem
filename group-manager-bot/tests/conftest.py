"""فیکسچرها — دیتابیس، ریپازیتوری، مترجم و «کارخانهٔ PluginHost»."""

from __future__ import annotations

import pytest

from bot.db.engine import Database
from bot.i18n.loader import Translator
from bot.repositories.sqlite_repo import SqliteGroupRepo, SqliteRoleRepo, SqliteUserRepo


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


@pytest.fixture()
def repos(db):
    return (
        SqliteGroupRepo(db),
        SqliteRoleRepo(db),
        SqliteUserRepo(db),
    )


@pytest.fixture()
def translator():
    return Translator()
