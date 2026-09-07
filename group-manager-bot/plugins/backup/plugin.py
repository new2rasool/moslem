"""پلاگین backup — پشتیبان‌گیری/بازیابی تنظیمات گروه.

ادمین با «backup» یک نسخهٔ JSON از همهٔ تنظیمات گروه (قفل‌ها، فیلترها،
یادداشت‌ها، کلمات سیاه، وضعیت پلاگین‌ها و…) می‌گیرد و با «restore <json>»
برمی‌گرداند. مقادیر با اعتبارسنجی نوع بازگشتی (فقط str/int/float/bool/
list/dict/None) بارگذاری می‌شوند تا ورودی مخرب رد شود.
"""

from __future__ import annotations

import json

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

MAX_SAFE = 3800


def _clean(value, depth: int = 0):
    """اعتبارسنجی/بازسازی مقادیر قابل‌ذخیره (رد انواع ناامن)."""
    if depth > 6:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            kk = _clean(k, depth + 1)
            vv = _clean(v, depth + 1)
            if isinstance(kk, str) and vv is not None:
                out[kk] = vv
        return out
    if isinstance(value, list):
        out = []
        for v in value:
            vv = _clean(v, depth + 1)
            if vv is not None:
                out.append(vv)
        return out
    return None


def _payload(api, chat_id) -> str:
    group = api.groups.get(chat_id)
    data = dict(group.settings) if group is not None else {}
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def register(api) -> None:
    async def cmd_backup(ctx):
        chat_id = ctx.chat_id
        text = _payload(api, chat_id)
        if len(text) > MAX_SAFE:
            ctx.respond(api.tr(ctx.lang, "too_large", size=len(text),
                               max=MAX_SAFE))
            return
        # ذخیرهٔ یک نسخه در کش برای بازیابیِ آسان‌تر (۲۴ ساعت)
        api.cache.set(f"backup:{chat_id}", text, ttl_s=86400)
        ctx.respond(api.tr(ctx.lang, "done", size=len(text)) + "\n" +
                    f"<code>{text}</code>")

    async def cmd_restore(ctx):
        chat_id = ctx.chat_id
        raw = (ctx.args or "").strip()
        if not raw:
            # تلاش از نسخهٔ کش
            cached = api.cache.get(f"backup:{chat_id}")
            if cached:
                raw = cached
        if not raw:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        # جداکردن JSON از داخل <code> اگر چسبیده باشد
        if raw.startswith("<code>") and raw.endswith("</code>"):
            raw = raw[len("<code>"):-len("</code>")]
        try:
            data = json.loads(raw)
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "bad_json"))
            return
        data = _clean(data)
        if not isinstance(data, dict):
            ctx.respond(api.tr(ctx.lang, "bad_shape"))
            return
        from bot.repositories.base import Group

        group = api.groups.get(chat_id)
        if group is None:
            group = Group(chat_id=chat_id, settings={})
        group.settings = data
        api.groups.upsert(group, merge_settings=False)
        ctx.respond(api.tr(ctx.lang, "restored", n=len(data)))

    api.register_command("backup", cmd_backup, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("backup", "پشتیبان‌گیری"))
    api.register_command("restore", cmd_restore, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("restore", "بازیابی"),
                         usage="restore <json> (یا بدون آرگومان از نسخهٔ کش)")


def on_unload(api) -> None:
    pass
