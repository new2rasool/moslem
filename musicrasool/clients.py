"""
MusicRasool - MTProto clients (single MTProto library: Pyrogram).

  app   -> the BOT  (bot_token) - handles commands, panels, buttons
  ubot  -> the HELPER userbot (phone session) - joins voice chats
           and streams audio/video through PyTgCalls
  call_py -> PyTgCalls wrapper around the helper userbot

ONLY Pyrogram is used as the MTProto client (no Telethon mixed in).
"""
import os

from pyrogram import Client
from pytgcalls import PyTgCalls

import config

# ------------------------------------------------------------------
# ntgcalls compatibility shim.
# py-tgcalls 1.2.9 expects ntgcalls.StreamStatus with title-case
# members (Playing/Paused/Idling) - ntgcalls 1.1.x provides those and
# ntgcalls 1.2.x renamed them to uppercase. Normalize both here so the
# bot works with either version.
# ------------------------------------------------------------------
try:
    from ntgcalls import StreamStatus as _SS, InputMode as _IM
    for _title, _upper in (("Playing", "PLAYING"), ("Paused", "PAUSED"), ("Idling", "IDLING")):
        if not hasattr(_SS, _title) and hasattr(_SS, _upper):
            setattr(_SS, _title, getattr(_SS, _upper))
    for _title, _upper in (
        ("Shell", "SHELL"),
        ("File", "FILE"),
        ("FFmpeg", "FFMPEG"),
        ("NoLatency", "NO_LATENCY"),
    ):
        if not hasattr(_IM, _title) and hasattr(_IM, _upper):
            setattr(_IM, _title, getattr(_IM, _upper))
except Exception:
    pass

cfg = config.get_config()

SESSION_DIR = cfg.SESSION_DIR
os.makedirs(SESSION_DIR, exist_ok=True)

app = Client(
    name="bot",
    api_id=cfg.API_ID,
    api_hash=cfg.API_HASH,
    bot_token=cfg.BOT_TOKEN,
    workdir=SESSION_DIR,
    device_model="MusicRasool",
    app_version="1.0.0",
    sleep_threshold=60,
)

ubot = Client(
    name="helper",
    api_id=cfg.API_ID,
    api_hash=cfg.API_HASH,
    workdir=SESSION_DIR,
    device_model="MusicRasool Helper",
    app_version="1.0.0",
    system_version="GNU/Linux",
    sleep_threshold=60,
)

call_py = PyTgCalls(ubot)

# ------------------------------------------------------------------
# ntgcalls 1.2.x returns UPPERCASE enum members (PLAYING) while
# py-tgcalls 1.2.9's per-instance `_conversions` table only knows the
# title-case members (Playing). Add the uppercase aliases to the
# INSTANCE table so `call_py.calls` / `call_py.active_calls` never
# raise KeyError on ntgcalls 1.2.x.
# ------------------------------------------------------------------
try:
    from ntgcalls import StreamStatus as _SS2

    _conv2 = call_py._conversions
    for _key2, _val2 in list(_conv2.items()):
        _nm2 = getattr(_key2, "name", "")
        if _nm2:
            _up2 = getattr(_SS2, _nm2.upper(), None)
            if _up2 is not None and _up2 not in _conv2:
                _conv2[_up2] = _val2
except Exception:
    pass

HELPER_SESSION = os.path.join(SESSION_DIR, "helper.session")


def helper_session_exists() -> bool:
    return os.path.exists(HELPER_SESSION)
