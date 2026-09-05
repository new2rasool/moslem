"""
MusicRasool - configuration loader + first-run console wizard.

Reads credentials from `.env` (or environment variables). On first run,
if no `.env` exists, an interactive wizard collects:
  - API_ID / API_HASH
  - BOT_TOKEN
  - OWNER_ID / SUDO_ID
and writes `.env`, then optionally logs in the HELPER userbot
(phone number + login code) and saves its session.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")


def _load_dotenv():
    """Minimal .env parser (no external dependency)."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _get(key: str, default=None):
    return os.environ.get(key, default)


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


class Config:
    def __init__(self):
        self.API_ID = int(_get("API_ID", 0) or 0)
        self.API_HASH = _get("API_HASH", "") or ""
        self.BOT_TOKEN = _get("BOT_TOKEN", "") or ""
        self.OWNER_ID = int(_get("OWNER_ID", 0) or 0)
        self.SUDO_ID = int(_get("SUDO_ID", 0) or 0)
        self.DOWNLOAD_DIR = _get("DOWNLOAD_DIR", "downloads")
        self.DEFAULT_LANG = _get("DEFAULT_LANG", "fa")
        self.MELOBIT_API = _get("MELOBIT_API", "https://api.melobit.com/v1")

        self.SESSION_DIR = os.path.join(BASE_DIR, "sessions")
        self.ASSETS_DIR = os.path.join(BASE_DIR, "assets")
        self.DB_PATH = os.path.join(BASE_DIR, "database.sqlite")

        os.makedirs(self.SESSION_DIR, exist_ok=True)
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(self.ASSETS_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    def is_complete(self) -> bool:
        return bool(
            self.API_ID
            and self.API_HASH
            and self.BOT_TOKEN
            and self.OWNER_ID
        )

    # ------------------------------------------------------------------
    def save_env(self, lines: dict):
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(
                "# MusicRasool configuration (auto-generated on first run)\n"
            )
            for key, value in lines.items():
                f.write(f"{key}={value}\n")
        # re-apply to environment
        for key, value in lines.items():
            os.environ[key] = str(value)
        print(f"  .env written to {ENV_FILE}")

    # ------------------------------------------------------------------
    def run_wizard(self):
        """Interactive first-run setup. Returns True when config is usable."""
        print("=" * 56)
        print("  MusicRasool - First Run Setup Wizard")
        print("=" * 56)
        print("  You need (all free):")
        print("   - API_ID & API_HASH : https://my.telegram.org")
        print("   - BOT_TOKEN         : https://t.me/BotFather")
        print("   - your numeric ID   : https://t.me/userinfobot")
        print("-" * 56)

        api_id = _input("API_ID          : ")
        api_hash = _input("API_HASH        : ")
        token = _input("BOT_TOKEN       : ")
        owner = _input("OWNER_ID        : ")
        sudo = _input("SUDO_ID (or owner id): ") or owner
        lang = _input("DEFAULT_LANG [fa/en] (default fa): ") or "fa"

        try:
            api_id = int(api_id)
            owner = int(owner)
            sudo = int(sudo)
        except ValueError:
            print("[!] API_ID / OWNER_ID / SUDO_ID must be numbers.")
            return False

        if not (api_id and api_hash and token and owner):
            print("[!] All fields are required.")
            return False

        self.API_ID = api_id
        self.API_HASH = api_hash
        self.BOT_TOKEN = token
        self.OWNER_ID = owner
        self.SUDO_ID = sudo
        self.DEFAULT_LANG = lang if lang in ("fa", "en") else "fa"

        self.save_env(
            {
                "API_ID": api_id,
                "API_HASH": api_hash,
                "BOT_TOKEN": token,
                "OWNER_ID": owner,
                "SUDO_ID": sudo,
                "DEFAULT_LANG": self.DEFAULT_LANG,
                "DOWNLOAD_DIR": self.DOWNLOAD_DIR,
                "MELOBIT_API": self.MELOBIT_API,
            }
        )
        return True


def load_config() -> Config:
    _load_dotenv()
    cfg = Config()
    if not cfg.is_complete():
        print("[i] Configuration incomplete. Starting setup wizard ...\n")
        ok = cfg.run_wizard()
        if not ok:
            print("[!] Setup failed. Edit .env manually and re-run.")
            sys.exit(1)
        # reload after wizard
        _load_dotenv()
        cfg = Config()
    return cfg


def get_config() -> Config:
    _load_dotenv()
    return Config()
