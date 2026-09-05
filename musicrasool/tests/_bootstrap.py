"""
Test bootstrap - MUST be imported before `config` in every test file.

Why this exists
---------------
Previously every test file did:

    os.chdir(PROJECT_ROOT)
    with open(".env", "w") as f: ...      # <-- overwrote the REAL .env
    database.init_db()
    database.execute("DELETE FROM charge")  # <-- wiped the REAL database

so running `python tests/run_all.py` on a live deployment replaced the bot
token / OWNER_ID and deleted every group charge, install, admin, sudo and
ban record. That was a data-loss bug in the test harness itself.

This module redirects every writable path into a fresh temporary directory
*before* any project module is imported, so the test suite can never touch
the developer's `.env`, `database.sqlite`, `sessions/` or `downloads/`.
"""
import atexit
import os
import shutil
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ----------------------------------------------------------------------
# A private sandbox for this test process
# ----------------------------------------------------------------------
TEST_ROOT = tempfile.mkdtemp(prefix="musicrasool-test-")
TEST_DB = os.path.join(TEST_ROOT, "database.sqlite")
TEST_DOWNLOADS = os.path.join(TEST_ROOT, "downloads")
TEST_SESSIONS = os.path.join(TEST_ROOT, "sessions")
os.makedirs(TEST_DOWNLOADS, exist_ok=True)
os.makedirs(TEST_SESSIONS, exist_ok=True)

# Credentials are supplied through the environment (config._load_dotenv uses
# os.environ.setdefault, so real environment values are never overwritten and
# no .env file is created anywhere).
os.environ.setdefault("API_ID", "1234567")
os.environ.setdefault("API_HASH", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("OWNER_ID", "6173234874")
os.environ.setdefault("SUDO_ID", "6173234874")
os.environ.setdefault("DEFAULT_LANG", "fa")
os.environ["DOWNLOAD_DIR"] = TEST_DOWNLOADS

# Redirect the module-level paths BEFORE `config` builds its first Config.
import config  # noqa: E402

config.BASE_DIR = TEST_ROOT
config.ENV_FILE = os.path.join(TEST_ROOT, ".env")   # deliberately never created

# Run from the sandbox so relative paths can not escape into the project.
os.chdir(TEST_ROOT)

# The real card media lives in the repository - mirror it into the sandbox so
# `utils.send_card` behaves exactly like production during tests.
_real_assets = os.path.join(PROJECT_ROOT, "assets")
if os.path.isdir(_real_assets):
    shutil.copytree(_real_assets, os.path.join(TEST_ROOT, "assets"), dirs_exist_ok=True)

# A helper "session" file inside the sandbox, for tests that need
# helper_session_exists() to be True.
HELPER_SESSION = os.path.join(TEST_SESSIONS, "helper.session")


def make_helper_session():
    """Pretend the helper account is logged in (inside the sandbox)."""
    open(HELPER_SESSION, "w").close()
    return HELPER_SESSION


def drop_helper_session():
    try:
        os.remove(HELPER_SESSION)
    except FileNotFoundError:
        pass


def _cleanup():
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


atexit.register(_cleanup)


def finish(code=0):
    """Flush output, remove the temp sandbox, then hard-exit.

    Every test file ends with `os._exit()` on purpose - it avoids a hang in
    pyrogram's client teardown at interpreter shutdown. But `os._exit()` also
    skips `atexit` handlers, so the `atexit.register(_cleanup)` above never ran
    and each run left its ~600 KB sandbox behind in /tmp, accumulating without
    bound across repeated runs. Call this instead of `os._exit()` directly.
    """
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    _cleanup()
    os._exit(code)
