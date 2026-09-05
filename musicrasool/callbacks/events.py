"""
PyTgCalls event handlers - robust stream lifecycle.

Why this file is important:
  - `leave_group_call()` internally calls `binding.stop()`, and ntgcalls
    fires the native stream-end callback for EVERY stopped stream. That
    means a stale "stream ended" event for the PREVIOUS song can arrive
    a moment AFTER the next song has started, which would make the bot
    leave the voice chat a few seconds into playback.
  - Fixes:
      * an "ignore window" right after every join (stale events dropped),
      * a generation counter so we only ever touch the CURRENT stream,
      * playlists are left to their own runner,
      * a short stream that ended way too early (bad/partial file,
        transient failure) is automatically re-joined (up to 2 retries)
        instead of leaving the call.
"""
import logging
import os
import time

import utils
from clients import call_py

logger = logging.getLogger("musicrasool.events")


@call_py.on_stream_end()
async def stream_end(client, update):
    """Handle a native stream-end event (audio or video)."""
    chat_id = update.chat_id
    try:
        entry = utils.STREAMS.get(chat_id)
        if entry is None:
            # we are not tracking this chat (e.g. playlist tracks) - nothing to do
            return

        now = time.time()

        # Stale event right after a (re)join: this is almost always the
        # PREVIOUS stream being stopped by our own leave_group_call.
        if now < entry.get("ignore_until", 0):
            return

        # A playlist runner is controlling this chat - let it handle the
        # next track instead of leaving the call.
        if chat_id in utils.PLAYLIS:
            return

        # ------------------------------------------------------------
        # The CURRENT stream truly ended. Decide: was it too early?
        # ------------------------------------------------------------
        elapsed = now - entry.get("started_at", now)
        dur = entry.get("duration")

        early = (
            (dur is None and elapsed < 20)
            or (dur and elapsed < max(10.0, dur * 0.5))
        )

        if early and entry.get("retries", 0) < 2:
            # Automatic recovery for premature ends (network blip,
            # ffmpeg hiccup, partially-downloaded file retry, ...).
            entry["retries"] = entry.get("retries", 0) + 1
            entry["started_at"] = now
            entry["ignore_until"] = now + 6
            logger.info("Stream ended early in %s - retrying (%s/2)", chat_id, entry["retries"])
            try:
                await utils.rejoin_stream(chat_id, entry)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Early-end retry failed for %s: %s", chat_id, exc)

        # ------------------------------------------------------------
        # Natural end (or retries exhausted) -> clean up + leave
        # ------------------------------------------------------------
        old = utils.clear_streaming(chat_id)
        if old and os.path.isfile(str(old)):
            try:
                os.remove(old)
            except Exception:
                pass
        try:
            await client.leave_group_call(chat_id)
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("stream_end cleanup failed: %s", exc)
