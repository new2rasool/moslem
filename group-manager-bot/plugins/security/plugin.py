"""پلاگین security — پنل امنیت گروه (نمای وضعیت + سوییچ محافظت‌ها).

گزارش وضعیت همهٔ محافظت‌های گروه را از تنظیمات همان گروه می‌خواند (کلیدهای
X_on با پیش‌فرض‌های دقیقِ همان پلاگین‌ها) و مدیر می‌تواند هر کدام را با
«security <نام> <on|off>» روشن/خاموش کند.

نام‌ها: captcha، joinapprove، newcomer، slowmode، automod، posthours،
antiraid، antirepeat، wordguard، locks، antiflood.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

# (کلید تنظیمات، برچسب فارسی، پیش‌فرضِ پلاگینِ اصلی وقتی کلید موجود نباشد)
PROTECTIONS: list[tuple[str, str, bool]] = [
    ("captcha_on", "کپچای ورود", False),
    ("ja_on", "گیت تأیید ورود", False),
    ("ng_on", "گارد تازه‌واردان", False),
    ("slowmode_on", "حالت آرام", False),
    ("automod_on", "تشدید خودکار مجازات", False),
    ("posthours_on", "محدودیت ساعات ارسال", False),
    ("raid_on", "ضد راید", True),
    ("repeat_on", "ضد تکرار/کپی‌پیست", True),
    ("wg_on", "فیلتر کلمات ممنوع گروه", True),
    ("locks_on", "قفل لینک/رسانه", True),
    ("flood_on", "ضد سیل", True),
]

NAME_TO_KEY = {
    "captcha": "captcha_on", "joinapprove": "ja_on", "newcomer": "ng_on",
    "slowmode": "slowmode_on", "automod": "automod_on", "posthours": "posthours_on",
    "antiraid": "raid_on", "antirepeat": "repeat_on", "wordguard": "wg_on",
    "locks": "locks_on", "antiflood": "flood_on",
}
KEY_TO_INDEX = {key: i for i, (key, _, _) in enumerate(PROTECTIONS)}


def _get(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    return group.settings.get(key, default) if group else default


def _put(api, chat_id, key, value) -> None:
    from bot.repositories.base import Group

    group = api.groups.get(chat_id)
    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)


def register(api) -> None:
    async def cmd_security(ctx):
        chat_id = ctx.chat_id
        if chat_id is None:
            ctx.respond(api.tr(ctx.lang, "group_only"))
            return
        parts = (ctx.args or "").split()
        if not parts:
            lines = [api.tr(ctx.lang, "header")]
            for key, label, default in PROTECTIONS:
                on = _get(api, chat_id, key, default)
                mark = "🟢" if on else "🔴"
                st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
                lines.append(f"{mark} {label}: {st}")
            lines.append(api.tr(ctx.lang, "hint"))
            ctx.respond("\n".join(lines))
            return

        name = parts[0].lower()
        key = NAME_TO_KEY.get(name, name)
        if key not in KEY_TO_INDEX:
            ctx.respond(api.tr(ctx.lang, "unknown", names="، ".join(NAME_TO_KEY)))
            return
        _, label, default = PROTECTIONS[KEY_TO_INDEX[key]]
        value = parts[1].lower() if len(parts) >= 2 else ""
        if value in ("on", "روشن"):
            _put(api, chat_id, key, True)
            ctx.respond(api.tr(ctx.lang, "toggled", label=label,
                               state=api.tr(ctx.lang, "on")))
        elif value in ("off", "خاموش"):
            _put(api, chat_id, key, False)
            ctx.respond(api.tr(ctx.lang, "toggled", label=label,
                               state=api.tr(ctx.lang, "off")))
        else:
            on = _get(api, chat_id, key, default)
            mark = "🟢" if on else "🔴"
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "single", label=label, state=f"{mark} {st}"))

    api.register_command("security", cmd_security, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("security", "امنیت"),
                         usage="security [<نام> <on|off>]")


def on_unload(api) -> None:
    pass
