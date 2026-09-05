"""
Command-routing regression tests.

`پخش ویدیو` (+reply) used to be swallowed by `play_dedicate`, because both
handlers match the `پخش ` prefix and pyrogram runs handlers in registration
order inside a group. That class of bug is invisible to every other test here:
each handler works in isolation, the collision only shows up in the dispatcher.

So this file walks the REAL `app.dispatcher.groups`, evaluates the real
`h.filters(app, m)` for each registered handler, and checks that every command
a handler declares in its own regex actually reaches that handler.

Handlers that deliberately hand the message on (`m.continue_propagation()` or
`raise ContinuePropagation`) are detected from their own AST, so they are not
reported as hijacking a later handler.

Run directly:      python tests/test_routing.py
Run with suite:    python tests/run_all.py
"""
import ast
import asyncio
import os
import re
import sys

import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)
from _bootstrap import PROJECT_ROOT

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from pyrogram import enums  # noqa: E402
from pyrogram.types import Chat, Message, User  # noqa: E402

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()

import handlers.admin_panel  # noqa: E402,F401
import handlers.auth  # noqa: E402,F401
import handlers.group_admin  # noqa: E402,F401
import handlers.misc  # noqa: E402,F401
import handlers.playback  # noqa: E402,F401
import handlers.private  # noqa: E402,F401
import handlers.tv  # noqa: E402,F401
import convo  # noqa: E402,F401
from clients import app  # noqa: E402

def flush_registrations():
    """Wait until every @app.on_message handler is actually registered.

    pyrogram's `Dispatcher.add_handler` does `self.loop.create_task(fn())`, so
    the append into `dispatcher.groups` only happens once the loop runs. Any
    probe that inspects `groups` before giving the loop a turn sees an empty
    table - and then never runs the loop, because there is nothing to iterate.
    """
    for _ in range(500):
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        if not pending:
            return
        loop.run_until_complete(asyncio.sleep(0))


flush_registrations()

results = []


def check(name, ok, extra=""):
    results.append((name, bool(ok)))
    if not ok:
        print(f"  [FAIL] {name}" + (f"  {extra}" if extra else ""))


GROUP = Chat(id=-1001234567890, type=enums.ChatType.SUPERGROUP, title="T")
PRIVATE = Chat(id=6173234874, type=enums.ChatType.PRIVATE)
USER = User(id=6173234874, first_name="O", is_bot=False, is_verified=False,
            is_restricted=False, is_deleted=False, is_self=False)
USER._client = app
# filters.command reads client.me.username
app.me = type("Me", (), {"username": "test_bot", "id": 999, "first_name": "B"})()


def msg(text, reply=False, private=False):
    m = Message(client=app, id=1, chat=(PRIVATE if private else GROUP),
                from_user=USER, text=text)
    if reply:
        r = Message(client=app, id=0, chat=m.chat, from_user=USER)
        r.audio = type("A", (), {"file_name": "s.mp3", "duration": 100, "title": "S"})()
        r.voice = None
        r.video = None
        r.document = None
        r.photo = None
        m.reply_to_message = r
        # pyrogram 2.0.106: filters.reply tests reply_to_message_id, NOT
        # reply_to_message. Setting only the object makes every filters.reply
        # handler return False and silently produces a wrong routing table.
        m.reply_to_message_id = 99
    return m


# ---------------------------------------------------------------- helpers
def matches(m):
    """All handlers whose filter matches, in dispatch order."""
    out = []
    for g in sorted(app.dispatcher.groups):
        for h in app.dispatcher.groups[g]:
            if loop.run_until_complete(h.filters(app, m)):
                out.append(getattr(h.callback, "__name__", "?"))
    return out


def continues_propagation(fn_name):
    """True when a handler's own source hands the message on to later handlers."""
    for fn in HANDLER_SOURCES:
        if fn[0] != fn_name:
            continue
        try:
            tree = ast.parse(fn[1])
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "continue_propagation":
                return True
            if isinstance(node, ast.Raise) and node.exc is not None:
                if "ContinuePropagation" in ast.unparse(node.exc):
                    return True
    return False


def _source_with_decorators(src, node):
    """Source of a function INCLUDING its decorators.

    `ast.get_source_segment` starts at the `def` line, which would hide a
    negative lookahead that lives in the `@app.on_message(...)` decorator -
    exactly where the routing filters are.
    """
    lines = src.splitlines()
    start = node.lineno
    for dec in getattr(node, "decorator_list", []):
        start = min(start, dec.lineno)
    end = getattr(node, "end_lineno", node.lineno)
    return "\n".join(lines[start - 1:end])


HANDLER_SOURCES = []
for rel in ("handlers/playback.py", "handlers/tv.py", "handlers/misc.py",
            "handlers/group_admin.py", "handlers/private.py", "handlers/auth.py",
            "handlers/admin_panel.py", "convo.py"):
    src = open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            HANDLER_SOURCES.append((node.name, _source_with_decorators(src, node)))


def literals(rx):
    """Turn a pyrogram command regex into [(text, anchored), ...].

    Each top-level alternative is normalised on its own, because a regex like
    `^(نصب)$|^(حذف)$` carries an anchor per alternative - stripping the anchors
    from the whole string first would lose them.

    `anchored` is True when the alternative ends in `$`, i.e. it matches only
    that exact text and therefore can never swallow a longer command.
    """
    core = re.sub(r"\(\?<?[=!][^)]*\)", "", rx)   # lookarounds FIRST
    out = []
    for alt in core.split("|"):
        alt = alt.strip()
        if not alt:
            continue
        anchored = alt.endswith("$")
        alt = alt.lstrip("^").rstrip("$").strip()
        alt = re.sub(r"^\((.*)\)$", r"\1", alt)    # unwrap the group
        alt = re.sub(r"\[[^\]]*\]", "", alt)        # character classes
        alt = re.sub(r"\s+", " ", alt).strip()
        if alt and re.fullmatch(r"[A-Za-zآ-ی\s]+", alt):
            out.append((alt, anchored))
    return out


def declared_commands():
    """(command, needs_reply, scope, handler) for every regex command declared."""
    found = []
    for rel in ("handlers/playback.py", "handlers/tv.py", "handlers/misc.py",
                "handlers/group_admin.py"):
        tree = ast.parse(open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in node.decorator_list:
                dsrc = ast.unparse(dec)
                if "on_message" not in dsrc:
                    continue
                needs_reply = "filters.reply" in dsrc
                scope = ("private" if "filters.private" in dsrc else
                         "group" if "filters.group" in dsrc else "any")
                # read the regex strings off the AST - ast.unparse() rewrites raw
                # strings with single quotes, so text-matching the dump finds none
                for c in ast.walk(dec):
                    if not (isinstance(c, ast.Constant) and isinstance(c.value, str)):
                        continue
                    rx = c.value
                    if "^" not in rx and not any(ch in rx for ch in "()[]|"):
                        continue
                    for lit, anchored in literals(rx):
                        if len(lit) >= 2:
                            found.append((lit, needs_reply, scope, node.name, anchored))
    seen, uniq = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def test_every_declared_command_is_reachable():
    print("\n-- every declared command reaches the handler that declared it --")
    unreachable = []
    for cmd, needs_reply, scope, owner, _anchored in sorted(declared_commands()):
        hit = False
        for text in (cmd, cmd + " @someone"):
            m = msg(text, reply=needs_reply, private=(scope == "private"))
            for name in matches(m):
                if name == owner:
                    hit = True
                    break
                if continues_propagation(name):
                    continue          # this one hands the message on
                break                 # this one consumes it
            if hit:
                break
        check(f"'{cmd}' reaches {owner}", hit, f"reply={needs_reply} scope={scope}")
        if not hit:
            unreachable.append((cmd, owner, scope, needs_reply))
    if unreachable:
        for c, o, sc, r in unreachable:
            print(f"         '{c}' -> {o} (scope={sc}, reply={r})")


def test_known_collisions_stay_fixed():
    """The exact collisions found by hand - pinned so they cannot come back."""
    print("\n-- pinned routing table (the P1 bug class) --")
    cases = [
        # (text, reply, expected handler)
        ("پخش", True, "play_reply"),
        ("پخش @ali", True, "play_dedicate"),
        ("پخش ویدیو", True, "playvideo_reply"),
        ("پخش ویدیو @ali", True, "playvideo_dedicate"),
        ("پخش ویدیو @ali", False, "playvideo_dedicate"),
        ("پخش فایل downloads/x.mp3", False, "play_file_cmd"),
        ("پخش لینک http://a/b.mp3", False, "play_link"),
        ("پخش لینک ویدیو http://a/b.mp4", False, "play_link_video"),
        ("پخش خودکار آهنگ شاد", False, "autoplay"),
        ("پخش خودکار ویدیو آهنگ شاد", False, "autoplay_video"),
        ("پخش یوتیوب https://youtu.be/x", False, "youtube_play"),
        ("پخش لیست", False, "play_playlist"),
        ("سرچ آهنگ", False, "search_music"),
        ("سرچ یوتیوب آهنگ", False, "youtube_search"),
        ("پخش تیوی", False, "play_tv"),
        ("توقف تیوی", False, "stop_tv"),
        ("توقف پخش", False, "stopmusic"),
        ("توقف ویدیو", False, "stopvideo"),
        ("مکث", False, "pause_cmd"),
        ("ازسرگیری", False, "resume_cmd"),
        ("بیصدا", False, "mute_cmd"),
        ("باصدا", False, "unmute_cmd"),
        ("AutoPlayVideo happy song", False, "autoplay_video"),
        ("AutoPlay happy song", False, "autoplay"),
        ("PlayVideo @ali", True, "playvideo_dedicate"),
        ("Play @ali", True, "play_dedicate"),
    ]
    for text, is_reply, expected in cases:
        m = msg(text, reply=is_reply)
        got = matches(m)
        # the first handler that does not hand the message on is the one that runs
        runs = next((n for n in got if not continues_propagation(n)), None)
        check(f"'{text}'{'+reply' if is_reply else ''} -> {expected}", runs == expected,
              f"got {runs} (matches={got})")


def test_no_handler_swallows_a_sibling_prefix():
    """Every prefix-sharing handler pair must be separated by a lookahead."""
    print("\n-- prefix collisions between sibling handlers --")
    cmds = declared_commands()
    src_by_name = dict((n, s) for n, s in HANDLER_SOURCES)
    flagged = 0
    # group by scope+reply, then find commands that are a prefix of another
    for a, ra, sa, oa, a_anchored in cmds:
        if a_anchored:
            continue            # `^(نصب)$` cannot match `نصب موزیک`
        for b, rb, sb, ob, _b_anchored in cmds:
            if oa == ob or sa != sb or ra != rb:
                continue
            if b != a and b.startswith(a) and len(b) > len(a):
                # `a` is an unanchored prefix of `b`, so whichever is registered
                # first wins; the shorter one must exclude the longer one.
                src = src_by_name.get(oa, "")
                tail = b[len(a):].strip()
                if tail and tail not in src:
                    flagged += 1
                    check(f"'{a}' ({oa}) excludes the longer '{b}' ({ob})", False,
                          f"'{tail}' not found in {oa}'s filter/body")
    print(f"  (unanchored prefix pairs inspected; {flagged} without an exclusion)")


def main():
    print("=" * 60)
    print("COMMAND ROUTING TESTS")
    print("=" * 60)
    test_known_collisions_stay_fixed()
    test_every_declared_command_is_reachable()
    test_no_handler_swallows_a_sibling_prefix()


main()

failed = [r for r in results if not r[1]]
total = len(results)
print("\n========================================")
print(f"RESULT: {total - len(failed)}/{total} routing checks passed")
if failed:
    print("FAILED:", [r[0] for r in failed])
    sys.exit(1)
print("=== ROUTING TEST PASSED ===")
_bootstrap.finish(0)
