"""پلاگین safemode — فعال‌سازی/خاموش‌سازی یکجای محافظت‌های گروه.

«safemode on» همهٔ محافظت‌های دوتایی (کلیدهای *_on) را با یک فرمان روشن
می‌کند و «safemode off» آن‌ها را خاموش می‌کند. برای بازگردانیِ دقیق، پیش از
روشن‌کردن، وضعیتِ قبلی هر کلید در «safemode_prev» ذخیره و هنگام خاموش‌کردن
بازیابی می‌شود (کلیدهایی که از قبل نبودند حذف می‌شوند) تا تنظیمات دستیِ قبلی
از بین نرود.

این پلاگین فقط پرچم‌های روشن/خاموش را لمس می‌کند؛ آستانه‌ها و قفل‌های محتوایی
(مثل lock url) دست‌نخورده می‌مانند.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

# محافظت‌های دوتایی که safemode کنترل می‌کند (نام کلید تنظیمات = نام پلاگین)
SHIELD_KEYS = (
    "captcha_on",     # captcha
    "flood_on",       # antiflood
    "wg_on",          # wordguard
    "caps_on",        # capsguard
    "repeat_on",      # antirepeat
    "automod_on",     # automod
    "raid_on",        # antiraid
    "mf_on",          # mediaflood
    "nguard_on",      # nameguard
)

_MISSING = "~__missing__~"


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


def _active(api, chat_id) -> list[str]:
    return [k for k in SHIELD_KEYS if _get(api, chat_id, k, False)]


def register(api) -> None:
    async def cmd_safemode(ctx):
        chat_id = ctx.chat_id
        parts = (ctx.args or "").split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("on", "روشن"):
            group = api.groups.get(chat_id)
            settings = dict(group.settings) if group else {}
            prev, missing = {}, []
            for k in SHIELD_KEYS:
                if k in settings:
                    prev[k] = settings[k]
                else:
                    missing.append(k)
            _put(api, chat_id, "safemode_on", True)
            _put(api, chat_id, "safemode_prev", prev)
            _put(api, chat_id, "safemode_missing", missing)
            for k in SHIELD_KEYS:
                _put(api, chat_id, k, True)
            ctx.respond(api.tr(ctx.lang, "enabled", n=len(SHIELD_KEYS)))
        elif cmd in ("off", "خاموش"):
            prev = _get(api, chat_id, "safemode_prev", {}) or {}
            missing = _get(api, chat_id, "safemode_missing", []) or []
            if prev or missing:
                for k, v in prev.items():
                    _put(api, chat_id, k, v)
                group = api.groups.get(chat_id)
                if group is not None:
                    for k in missing:
                        group.settings.pop(k, None)
                    group.settings.pop("safemode_on", None)
                    group.settings.pop("safemode_prev", None)
                    group.settings.pop("safemode_missing", None)
                    api.groups.upsert(group, merge_settings=False)
            else:
                for k in SHIELD_KEYS:
                    _put(api, chat_id, k, False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            on = bool(_get(api, chat_id, "safemode_on", False))
            state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            active = _active(api, chat_id)
            if active:
                names = "، ".join(active)
            else:
                names = api.tr(ctx.lang, "none")
            ctx.respond(api.tr(ctx.lang, "status", state=state, names=names))

    api.register_command("safemode", cmd_safemode, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("safemode", "حالت امن"),
                         usage="safemode [on|off]")


def on_unload(api) -> None:
    pass
