"""تست‌های ریپازیتوری SQLite — نوشتن/خواندن گروه، نقش و کاربر."""

import pytest

from bot.repositories.base import Group, User


def test_group_upsert_and_get(repos):
    groups, _, _ = repos
    assert groups.get(-1001) is None
    groups.upsert(Group(chat_id=-1001, title="انجمن", lang="fa"))
    got = groups.get(-1001)
    assert got is not None
    assert got.title == "انجمن" and got.lang == "fa"
    assert got.approved is True and got.settings == {}


def test_group_upsert_merge_settings(repos):
    groups, _, _ = repos
    groups.upsert(Group(chat_id=-1001, settings={"antiflood": True, "captcha": False}))
    groups.upsert(Group(chat_id=-1001, settings={"captcha": True}))
    got = groups.get(-1001)
    assert got.settings == {"antiflood": True, "captcha": True}  # ادغام شد


def test_group_delete(repos):
    groups, _, _ = repos
    groups.upsert(Group(chat_id=-1001))
    assert groups.delete(-1001) is True
    assert groups.delete(-1001) is False
    assert groups.get(-1001) is None


def test_group_settings_bad_json_tolerated(db):
    from bot.repositories.sqlite_repo import SqliteGroupRepo

    with db.connection() as conn:
        conn.execute(
            "INSERT INTO groups (chat_id, title, settings) VALUES (?, ?, ?)",
            (-1, "x", "{not-json"),
        )
    repo = SqliteGroupRepo(db)
    assert repo.get(-1).settings == {}


def test_role_crud(repos):
    _, roles, _ = repos
    assert roles.get_role(-1001, 10) is None
    roles.set_role(-1001, 10, "mod", by_user=1)
    assert roles.get_role(-1001, 10) == "mod"
    roles.set_role(-1001, 10, "admin", by_user=1)  # ارتقا
    assert roles.get_role(-1001, 10) == "admin"
    assert roles.delete_role(-1001, 10) is True
    assert roles.delete_role(-1001, 10) is False


def test_role_invalid_raises(repos):
    _, roles, _ = repos
    with pytest.raises(ValueError):
        roles.set_role(-1001, 10, "king", by_user=1)


def test_role_scoped_per_chat(repos):
    _, roles, _ = repos
    roles.set_role(-1001, 10, "admin")
    assert roles.get_role(-1002, 10) is None


def test_list_roles_order(repos):
    _, roles, _ = repos
    roles.set_role(-1001, 1, "owner")
    roles.set_role(-1001, 2, "admin")
    listing = roles.list_roles(-1001)
    assert (1, "owner", "") in listing
    assert (2, "admin", "") in listing


def test_role_title(repos):
    _, roles, _ = repos
    roles.set_role(-1001, 7, "mod", title="ناظر شب")
    assert roles.get_role(-1001, 7) == "mod"
    assert roles.list_roles(-1001) == [(7, "mod", "ناظر شب")]


def test_user_crud(repos):
    _, _, users = repos
    assert users.get(777) is None
    users.upsert(User(777, lang="en"))
    users.upsert(User(777, lang="fa"))  # به‌روزرسانی
    got = users.get(777)
    assert got is not None and got.lang == "fa"
