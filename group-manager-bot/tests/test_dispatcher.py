"""تست‌های Dispatcher — پارس، سطح دسترسی، رویداد، دکمه و ایزوله‌سازی خطا."""

from __future__ import annotations

import pytest

from bot.context import CallbackContext, CommandContext, EventContext
from bot.domain.roles import AccessLevel
from bot.i18n.loader import Translator
from bot.registry import CommandBinding, EventBinding, CallbackBinding, Registry
from bot.services.access_service import AccessService


class DictRoleRepo:
    """جایگزین سبک RoleRepo برای تست (بدون SQLite)."""

    def __init__(self):
        self.data: dict[tuple[int, int], str] = {}

    def set_role(self, chat_id, user_id, role, by_user=0, title=""):
        self.data[(chat_id, user_id)] = role

    def get_role(self, chat_id, user_id):
        return self.data.get((chat_id, user_id))

    def delete_role(self, chat_id, user_id):
        return self.data.pop((chat_id, user_id), None) is not None

    def list_roles(self, chat_id):
        return [(u, r, "") for (c, u), r in self.data.items() if c == chat_id]


@pytest.fixture()
def dispatch():
    roles = DictRoleRepo()
    roles.set_role(-1001, 10, "admin", by_user=1)
    roles.set_role(-1001, 11, "mod", by_user=1)
    access = AccessService(roles, owner_id=1, sudo_ids=(2,))
    registry = Registry()
    from bot.dispatcher import Dispatcher

    return Dispatcher(registry, access, Translator(), default_lang="fa"), registry, access


async def _helper_echo(ctx: CommandContext) -> None:
    ctx.respond(f"echo:{ctx.command}:{ctx.args}")


# ── پارس و توزیع ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dispatch_by_prefix_and_alias(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="ban", handler=_helper_echo, level=AccessLevel.ADMIN, aliases=("بن",)))

    out = await d.try_dispatch_command("/ban 123", chat_id=-1001, user_id=10)
    assert out == ["echo:ban:123"]

    out = await d.try_dispatch_command("بن 456", chat_id=-1001, user_id=10)
    assert out == ["echo:ban:456"]

    out = await d.try_dispatch_command("!ban 789", chat_id=-1001, user_id=10)
    assert out == ["echo:ban:789"]


@pytest.mark.asyncio
async def test_two_word_persian_alias(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="gban", handler=_helper_echo, level=AccessLevel.SUDO, aliases=("بن سراسری",)))

    out = await d.try_dispatch_command("بن سراسری 123 دلیل", chat_id=-1001, user_id=1)
    assert out == ["echo:gban:123 دلیل"]


@pytest.mark.asyncio
async def test_plain_message_is_not_command(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="ban", handler=_helper_echo))
    out = await d.try_dispatch_command("سلام به همه", chat_id=-1001, user_id=1)
    assert out is None  # اصلاً فرمان نبود → بدون پاسخ


@pytest.mark.asyncio
async def test_unknown_prefixed_command(dispatch):
    d, _, _ = dispatch
    out = await d.try_dispatch_command("/nosuchcmd", chat_id=-1001, user_id=1, lang="fa")
    assert out and "ناشناخته" in out[0]


# ── سطح دسترسی ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_access_denied_for_normal_user(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="ban", handler=_helper_echo, level=AccessLevel.ADMIN))
    out = await d.try_dispatch_command("/ban x", chat_id=-1001, user_id=99)
    assert out and "دسترسی ندارید" in out[0]


@pytest.mark.asyncio
async def test_mod_cannot_run_admin_command(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="ban", handler=_helper_echo, level=AccessLevel.ADMIN))
    out = await d.try_dispatch_command("/ban x", chat_id=-1001, user_id=11)  # mod
    assert out and "دسترسی ندارید" in out[0]


@pytest.mark.asyncio
async def test_owner_and_sudo_pass(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="gban", handler=_helper_echo, level=AccessLevel.SUDO))
    assert await d.try_dispatch_command("/gban x", chat_id=-1001, user_id=1)  # مالک ربات
    assert await d.try_dispatch_command("/gban x", chat_id=-1001, user_id=2)  # سودو


@pytest.mark.asyncio
async def test_private_only_and_group_only(dispatch):
    d, registry, _ = dispatch
    registry.add_command(CommandBinding(name="secret", handler=_helper_echo, private_only=True))
    registry.add_command(CommandBinding(name="gcmd", handler=_helper_echo, group_only=True))

    out = await d.try_dispatch_command("/secret", chat_id=-1001, user_id=1)
    assert out and "پیوی" in out[0]
    assert await d.try_dispatch_command("/secret", chat_id=None, user_id=1, is_private=True)

    out = await d.try_dispatch_command("/gcmd", chat_id=None, user_id=1, is_private=True)
    assert out and "گروه" in out[0]
    assert await d.try_dispatch_command("/gcmd", chat_id=-1001, user_id=1)


# ── رویدادها ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_event_broadcast_priority_order(dispatch):
    d, registry, _ = dispatch
    order: list[str] = []

    async def first(ctx: EventContext):
        order.append("first")
        ctx.respond("A")

    async def second(ctx: EventContext):
        order.append("second")
        ctx.respond("B")

    registry.add_event(EventBinding(event="member_joined", handler=second, priority=10, plugin="p2"))
    registry.add_event(EventBinding(event="member_joined", handler=first, priority=100, plugin="p1"))

    out = await d.dispatch_event("member_joined", chat_id=-1001, lang="fa", data={"member_name": "علی"})
    assert order == ["first", "second"]  # اولویت بالاتر اول اجرا می‌شود
    assert out == ["A", "B"]


@pytest.mark.asyncio
async def test_event_error_isolation(dispatch):
    d, registry, _ = dispatch

    async def broken(ctx):
        raise RuntimeError("x")

    async def fine(ctx):
        ctx.respond("ok")

    registry.add_event(EventBinding(event="member_joined", handler=broken, plugin="bad"))
    registry.add_event(EventBinding(event="member_joined", handler=fine, plugin="good"))
    out = await d.dispatch_event("member_joined", chat_id=-1001, lang="fa")
    assert out == ["ok"]  # پلاگین سالم بعد از خراب هم اجرا شد


# ── دکمه‌ها (callback) ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_callback_longest_prefix_wins(dispatch):
    d, registry, _ = dispatch

    async def generic(ctx: CallbackContext):
        ctx.respond(f"generic:{ctx.payload}")

    async def specific(ctx: CallbackContext):
        ctx.respond(f"specific:{ctx.payload}")

    registry.add_callback(CallbackBinding(prefix="approve:", handler=generic, plugin="p1"))
    registry.add_callback(CallbackBinding(prefix="approve:confirm:", handler=specific, plugin="p2"))

    out = await d.dispatch_callback("approve:confirm:42", chat_id=-1001, user_id=5, lang="fa")
    assert out == ["specific:42"]

    # برای handler سراسری، payload شامل باقیماندهٔ کامل است
    out = await d.dispatch_callback("approve:42", chat_id=-1001, user_id=5, lang="fa")
    assert out == ["generic:42"]


@pytest.mark.asyncio
async def test_callback_unknown_returns_none(dispatch):
    d, _, _ = dispatch
    assert await d.dispatch_callback("nosuch:1", chat_id=-1001, user_id=1, lang="fa") is None


@pytest.mark.asyncio
async def test_command_handler_error_returns_error_message(dispatch):
    d, registry, _ = dispatch

    async def boom(ctx):
        raise RuntimeError("x")

    registry.add_command(CommandBinding(name="boom", handler=boom))
    out = await d.try_dispatch_command("/boom", chat_id=-1001, user_id=1)
    assert out and "خطایی" in out[0]
