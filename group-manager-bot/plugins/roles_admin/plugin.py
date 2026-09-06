"""پلاگین roles_admin — مدیریت نقش‌های رباتی در گروه (promote/demote/adminlist).

قواعد حرفه‌ای:
- فقط «سطح بالاتر» می‌تواند ارتقا/عزل دهد (هم‌سطح نه).
- ارتقا به «مالک گروه» فقط توسط مالک ربات/سودو (جلوگیری از کودتا).
- کاربر نمی‌تواند خودش را ارتقا دهد.
- هر ارتقا/عزل در دفتر حسابرسی ثبت و به کانال لاگ می‌رود.
"""

from __future__ import annotations

import re

from bot.domain.roles import (
    AccessLevel,
    DB_ROLE_TO_LEVEL,
    LEVEL_LABELS_EN,
    LEVEL_LABELS_FA,
)

PLUGIN_VERSION = "1.0.0"

_ID_RE = re.compile(r"^-?\d{2,}$")
ALLOWED_ROLES = ("mod", "admin", "co_owner")


def _resolve_target(ctx, api):
    if ctx.reply_to_user_id:
        return ctx.reply_to_user_id, None
    for token in ctx.args.split():
        if _ID_RE.match(token):
            return int(token), None
    return None, api.tr(ctx.lang, "err_no_target")


def register(api) -> None:
    async def cmd_promote(ctx):
        role = None
        rest = ctx.args
        for candidate in ALLOWED_ROLES:
            if rest.startswith(candidate):
                role = candidate
                rest = rest[len(candidate):].strip()
                break
        if role is None:
            # ممکن است «ارتقا admin @id» یا «ارتقا @id admin» — ساده: اولین توکنِ نقش
            tokens = rest.split()
            if tokens and tokens[0].lower() in ALLOWED_ROLES:
                role = tokens[0].lower()
                rest = " ".join(tokens[1:])
        if role is None:
            ctx.respond(api.tr(ctx.lang, "usage_promote"))
            return

        target_id, err = _resolve_target(ctx, api)
        if err:
            ctx.respond(err)
            return
        assert target_id is not None

        actor = api.access.level(ctx.chat_id, ctx.user_id)
        target_level_now = api.access.level(ctx.chat_id, target_id)
        role_level = DB_ROLE_TO_LEVEL[role]

        # قواعد
        if ctx.user_id == target_id:
            ctx.respond(api.tr(ctx.lang, "no_self"))
            return
        if target_level_now >= AccessLevel.OWNER and not api.access.is_bot_owner(ctx.user_id):
            ctx.respond(api.tr(ctx.lang, "cannot_touch_owner"))
            return
        # برای co_owner نیاز به CO_OWNER+؛ برای admin نیاز ADMIN+؛ برای mod نیاز MOD+
        if actor <= role_level:
            ctx.respond(api.tr(ctx.lang, "denied_hierarchy"))
            return
        if target_level_now >= actor and not api.access.is_bot_owner(ctx.user_id):
            ctx.respond(api.tr(ctx.lang, "denied_target_not_lower"))
            return

        api.roles.set_role(ctx.chat_id, target_id, role, by_user=ctx.user_id)
        await api.record_action(ctx.chat_id, "promote", target_id, ctx.user_id, reason=role)
        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        ctx.respond(api.tr(ctx.lang, "promoted", target=target_id, role=labels[role_level]))

    async def cmd_demote(ctx):
        target_id, err = _resolve_target(ctx, api)
        if err:
            ctx.respond(err)
            return
        assert target_id is not None
        if ctx.user_id == target_id:
            ctx.respond(api.tr(ctx.lang, "no_self"))
            return

        actor = api.access.level(ctx.chat_id, ctx.user_id)
        target_level_now = api.access.level(ctx.chat_id, target_id)
        if target_level_now is AccessLevel.USER:
            ctx.respond(api.tr(ctx.lang, "not_an_admin"))
            return
        if target_level_now >= AccessLevel.OWNER and not api.access.is_bot_owner(ctx.user_id):
            ctx.respond(api.tr(ctx.lang, "cannot_touch_owner"))
            return
        if target_level_now >= actor and not api.access.is_bot_owner(ctx.user_id):
            ctx.respond(api.tr(ctx.lang, "denied_target_not_lower"))
            return

        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        removed = api.roles.delete_role(ctx.chat_id, target_id)
        await api.record_action(
            ctx.chat_id, "demote", target_id, ctx.user_id,
            reason=f"{labels[target_level_now]} → {labels[AccessLevel.USER]}",
        )
        ctx.respond(
            api.tr(ctx.lang, "demoted", target=target_id, prev=labels[target_level_now])
            if removed else api.tr(ctx.lang, "not_an_admin")
        )

    async def cmd_adminlist(ctx):
        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        rows = api.roles.list_roles(ctx.chat_id)
        if not rows:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "header", n=len(rows))]
        for uid, role, title in rows:
            label = labels.get(DB_ROLE_TO_LEVEL.get(role, AccessLevel.USER), role)
            t = f" ({title})" if title else ""
            lines.append(f"• {uid} — {label}{t}")
        ctx.respond("\n".join(lines))

    api.register_command(
        "promote", cmd_promote, level=AccessLevel.ADMIN, group_only=True,
        aliases=("promote", "ارتقا"),
        usage="promote <mod|admin|co_owner> <@user|id> (یا ریپلای)",
    )
    api.register_command(
        "demote", cmd_demote, level=AccessLevel.ADMIN, group_only=True,
        aliases=("demote", "عزل"),
    )
    api.register_command(
        "adminlist", cmd_adminlist, group_only=True,
        aliases=("adminlist", "لیست مدیران"),
    )
