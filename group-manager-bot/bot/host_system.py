"""
فرمان‌های سیستمی میزبان (ثبت‌شده با نام "<core>") — بخشی از خودِ هسته.

این‌ها «قابلیت» نیستند؛ مدیریتِ خودِ چارچوب‌اند:
  /start · /help (فهرست پویا از پلاگین‌های بارگذاری‌شده)
  /plugins (وضعیت پلاگین‌ها) · /plugin load|unload|reload|reloadall <name>

نکته: /help هر بار از روی Registry ساخته می‌شود؛ یعنی با افزودن پلاگین جدید،
بی‌واسطه در فهرست ظاهر می‌شود — بدون تغییر هسته.
"""

from __future__ import annotations

from typing import Any

from bot.domain.roles import AccessLevel, LEVEL_LABELS_EN, LEVEL_LABELS_FA
from bot.plugin_api import PluginAPI


def register_core(api: PluginAPI) -> None:
    host: Any = api.host
    registry = api._registry  # فرمان‌های سیستم خودِ هسته‌اند؛ دسترسی مستقیم مجاز است
    tr = api.tr

    async def cmd_start(ctx):
        ctx.respond(api.tr(ctx.lang, "start_user", name=ctx.sender_name or ""))

    async def cmd_help(ctx):
        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        lines: list[str] = []
        by_plugin: dict[str, list] = {}
        for binding in sorted(
            registry.commands().values(), key=lambda b: (b.plugin, b.name)
        ):
            by_plugin.setdefault(binding.plugin, []).append(binding)
        total = sum(len(v) for v in by_plugin.values())
        header = api.tr(ctx.lang, "help_header", count=total, plugins=len(by_plugin))
        lines.append(header)
        for plugin_name in sorted(by_plugin):
            lines.append(f"┌ {plugin_name}")
            for b in by_plugin[plugin_name]:
                line = f"  /{b.name}"
                if b.aliases:
                    fa_alias = "، ".join(b.aliases[:4])
                    line += f"  ({fa_alias})"
                level_label = labels.get(b.level, b.level.name)
                line += f"  [{level_label}]"
                lines.append(line)
                if b.usage:
                    lines.append(api.tr(ctx.lang, "help_usage", usage=b.usage))
        lines.append(api.tr(ctx.lang, "help_footer"))
        ctx.respond("\n".join(lines))

    async def cmd_plugins(ctx):
        lines = [api.tr(ctx.lang, "plugins_header", n=len(host.records))]
        in_group = bool(ctx.chat_id and not ctx.is_private)
        for name in sorted(host.records):
            rec = host.records[name]
            if rec.failed:
                lines.append(f"❌ {name} — {rec.error}")
            elif rec.enabled:
                state = ""
                if in_group:
                    state = "🟢" if host.is_plugin_enabled(ctx.chat_id, name) else "🔴"
                lines.append(
                    f"{state} {name} v{rec.version}  |  {rec.commands} فرمان · "
                    f"{rec.events} رویداد · {rec.callbacks} دکمه"
                )
        lines.append(api.tr(ctx.lang, "plugins_total", n=len(registry.commands())))
        ctx.respond("\n".join(lines))

    async def cmd_plugin_group(ctx):
        parts = ctx.args.split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "plugin_group_usage"))
            return
        name, state = parts[0], parts[1].lower()
        if name not in host.records:
            ctx.respond(api.tr(ctx.lang, "plugin_not_found", name=name))
            return
        if state in ("on", "روشن", "1", "true"):
            enabled = True
        elif state in ("off", "خاموش", "0", "false"):
            enabled = False
        else:
            ctx.respond(api.tr(ctx.lang, "plugin_group_usage"))
            return
        host.set_plugin_enabled(ctx.chat_id, name, enabled)
        key = "plugin_ok_enabled" if enabled else "plugin_ok_disabled"
        ctx.respond(api.tr(ctx.lang, key, name=name))

    async def cmd_plugin_manage(ctx):
        parts = ctx.args.split()
        action = parts[0] if parts else "list"
        name = parts[1] if len(parts) > 1 else ""

        if action == "reloadall" or action in ("reload-all", "بارگذاری دوباره همه"):
            changed = host.reload_changed()
            ctx.respond(api.tr(ctx.lang, "plugin_reloaded_all", n=len(changed), names=", ".join(changed) or "—"))
            return

        if action in ("list", "فهرست"):
            await cmd_plugins(ctx)
            return

        target = host.records.get(name)
        ok = False
        if action in ("load", "بارگذاری"):
            if target and target.enabled:
                ctx.respond(api.tr(ctx.lang, "plugin_already", name=name, state="enabled"))
                return
            ok = host.load(name)
            msg_key = "plugin_ok_loaded" if ok else "plugin_load_fail"
        elif action in ("unload", "حذف"):
            if target is None:
                ctx.respond(api.tr(ctx.lang, "plugin_not_found", name=name))
                return
            ok = host.unload(name)
            msg_key = "plugin_ok_unloaded" if ok else "plugin_not_found"
        elif action in ("reload", "بارگذاری دوباره", "ری‌لود"):
            if target is None:
                ctx.respond(api.tr(ctx.lang, "plugin_not_found", name=name))
                return
            ok = host.reload(name)
            msg_key = "plugin_ok_reloaded" if ok else "plugin_load_fail"
        else:
            ctx.respond(api.tr(ctx.lang, "plugin_bad_action", action=action))
            return

        ctx.respond(api.tr(ctx.lang, msg_key, name=name))

    api.register_command("start", cmd_start, aliases=("start", "شروع", "استارت"))
    api.register_command("help", cmd_help, aliases=("help", "راهنما", "کمک"))
    api.register_command("plugins", cmd_plugins, aliases=("plugins", "پلاگین‌ها"))
    api.register_command(
        "plugin",
        cmd_plugin_manage,
        level=AccessLevel.SUDO,
        private_only=True,
        aliases=("plugin", "مدیریت پلاگین"),
        usage="plugin <list|load|unload|reload|reloadall> [name]",
    )
    api.register_command(
        "pluginenable",
        cmd_plugin_group,
        level=AccessLevel.ADMIN,
        group_only=True,
        aliases=("pluginenable", "فعال‌سازی پلاگین"),
        usage="pluginenable <name> <on|off>",
    )
