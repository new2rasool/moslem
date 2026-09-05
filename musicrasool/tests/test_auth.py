"""
Helper login flow test (phone -> code -> optional 2FA), fully mocked.

Verifies:
  1. /login asks for the phone number
  2. the /login command itself is NOT consumed by the wizard
  3. entering a phone calls send_code and asks for the code
  4. entering the code calls sign_in with the correct keyword args
     (Pyrogram 2.x order: phone_number, phone_code_hash, phone_code)
  5. success message + session state cleanup
  6. 2FA path: SessionPasswordNeeded -> password prompt -> check_password
  7. wrong code -> error message and the wizard stays for a retry
  8. /cancel aborts the wizard
"""
import asyncio
import os
import sys

import pyrogram

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

with open(".env", "w", encoding="utf-8") as f:
    f.write("API_ID=1234567\nAPI_HASH=0123456789abcdef0123456789abcdef\n")
    f.write("BOT_TOKEN=123456:TESTTOKEN\nOWNER_ID=6173234874\nSUDO_ID=6173234874\n")
    f.write("DEFAULT_LANG=fa\nDOWNLOAD_DIR=downloads\n")

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()

import handlers.private  # noqa: E402,F401
import handlers.auth as auth  # noqa: E402

# make sure no leftover session from other tests
_session_path = os.path.join(PROJECT_ROOT, "sessions", "helper.session")
if os.path.exists(_session_path):
    os.remove(_session_path)

OWNER = config.get_config().OWNER_ID
OWNER_USER_ID = OWNER


class FakeUser:
    def __init__(self, id):
        self.id = id
        self.first_name = "Mersad"

    def mention(self, name=None):
        return f"[{name or self.first_name}](tg://user?id={self.id})"


class FakeChat:
    def __init__(self, id):
        self.id = id


class FakeMessage:
    def __init__(self, user, text):
        self.from_user = user
        self.chat = FakeChat(user.id)
        self.text = text
        self.id = 1
        self.replies = []

    async def reply(self, text, **kw):
        self.replies.append(text)
        return self


class FakeSentCode:
    phone_code_hash = "HASH123"


class FakeTempClient:
    """Mocks the throwaway helper-login client."""

    def __init__(self):
        self.connected = False
        self.disconnected = False
        self.calls = []
        self.sign_in_behavior = "ok"  # ok | password | wrong_code
        self.check_password_behavior = "ok"  # ok | wrong

    async def connect(self):
        self.connected = True
        self.calls.append("connect")

    async def disconnect(self):
        self.disconnected = True
        self.calls.append("disconnect")

    async def send_code(self, phone):
        self.calls.append(("send_code", phone))
        return FakeSentCode()

    async def sign_in(self, **kw):
        self.calls.append(("sign_in", kw))
        if self.sign_in_behavior == "password":
            from pyrogram.errors import SessionPasswordNeeded
            raise SessionPasswordNeeded()
        if self.sign_in_behavior == "wrong_code":
            from pyrogram.errors import PhoneCodeInvalid
            raise PhoneCodeInvalid("x")
        return "OK_USER"

    async def check_password(self, password):
        self.calls.append(("check_password", password))
        if self.check_password_behavior == "wrong":
            from pyrogram.errors import BadRequest
            raise BadRequest("PASSWORD_HASH_INVALID")
        return "OK_USER"


class FakeBotClient:
    async def get_me(self):
        class Me:
            first_name = "TestBot"
        return Me()


results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


async def _call_flow(bot, m):
    """Call auth.login_flow like the dispatcher would, returning the outcome."""
    try:
        await auth.login_flow(bot, m)
        return "return"
    except pyrogram.ContinuePropagation:
        return "continue"
    except pyrogram.StopPropagation:
        return "stop"


async def main():
    bot = FakeBotClient()
    owner = FakeUser(OWNER_USER_ID)

    # ---------------------------------------------------------------
    # 1. /login command -> phone prompt
    # ---------------------------------------------------------------
    from handlers.private import login_cmd
    auth.LOGIN_STATE.clear()
    m = FakeMessage(owner, "/login")
    await login_cmd(bot, m)
    check("login asks for phone", any("شماره تلفن" in r for r in m.replies))
    check("login sets phone step", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "phone")

    # 2. the /login message itself must not be consumed by the wizard
    #    -> login_flow now re-raises ContinuePropagation so other handlers
    #       (the admin panel / commands) can process it
    res = await _call_flow(bot, m)
    check("login cmd not consumed", res == "continue")
    check("login wizard state kept", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "phone")
    check("login cmd no error reply", len(m.replies) == 1)

    # 3. no-state case must propagate (so panel buttons keep working)
    auth.LOGIN_STATE.clear()
    m_idle = FakeMessage(owner, "📊 وضعیت")
    res = await _call_flow(bot, m_idle)
    check("login_flow propagates when no wizard", res == "continue")
    check("login_flow leaves the message untouched", m_idle.replies == [])

    # 4. wrong phone (no +) -> error
    auth.LOGIN_STATE[OWNER_USER_ID] = {"step": "phone"}
    m2 = FakeMessage(owner, "0912")
    await auth.login_flow(bot, m2)
    check("phone without + rejected", "با +" in m2.replies[0])
    check("state still phone step", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "phone")

    # 4. valid phone -> send_code + code prompt
    fake = FakeTempClient()
    auth._temp_helper_client = lambda: fake
    m3 = FakeMessage(owner, "+989123456789")
    await auth.login_flow(bot, m3)
    check("send_code called with phone", ("send_code", "+989123456789") in fake.calls)
    check("code step set", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "code")
    check("code prompt sent", any("کد ورود" in r for r in m3.replies))

    # 5. code -> sign_in with correct keyword args
    m4 = FakeMessage(owner, "12345")
    await auth.login_flow(bot, m4)
    sign_calls = [c for c in fake.calls if isinstance(c, tuple) and c[0] == "sign_in"]
    check("sign_in called", len(sign_calls) == 1)
    kw = sign_calls[0][1]
    check("sign_in kwargs correct order",
          kw.get("phone_number") == "+989123456789"
          and kw.get("phone_code_hash") == "HASH123"
          and kw.get("phone_code") == "12345")
    check("temp client disconnected", fake.disconnected)
    check("state cleared after success", OWNER_USER_ID not in auth.LOGIN_STATE)
    check("success message sent", any("با موفقیت" in r for r in m4.replies))

    # 6. 2FA path
    auth.LOGIN_STATE.clear()
    fake2 = FakeTempClient()
    fake2.sign_in_behavior = "password"
    auth._temp_helper_client = lambda: fake2
    auth.LOGIN_STATE[OWNER_USER_ID] = {"step": "phone"}
    m5 = FakeMessage(owner, "+989123456789")
    await auth.login_flow(bot, m5)
    m6 = FakeMessage(owner, "12345")
    await auth.login_flow(bot, m6)
    check("2FA password prompt", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "password")
    check("2FA prompt text", any("رمز" in r for r in m6.replies))
    m7 = FakeMessage(owner, "mypassword")
    await auth.login_flow(bot, m7)
    check("check_password called", ("check_password", "mypassword") in fake2.calls)
    check("2FA success clears state", OWNER_USER_ID not in auth.LOGIN_STATE)

    # 7. wrong code -> retry
    auth.LOGIN_STATE.clear()
    fake3 = FakeTempClient()
    fake3.sign_in_behavior = "wrong_code"
    auth._temp_helper_client = lambda: fake3
    auth.LOGIN_STATE[OWNER_USER_ID] = {"step": "phone"}
    m8 = FakeMessage(owner, "+989123456789")
    await auth.login_flow(bot, m8)
    m9 = FakeMessage(owner, "00000")
    await auth.login_flow(bot, m9)
    check("wrong code error", any("صحیح نیست" in r for r in m9.replies))
    check("wizard stays for retry", auth.LOGIN_STATE.get(OWNER_USER_ID, {}).get("step") == "code")

    # 8. /cancel aborts
    from handlers.private import cancel_cmd
    m10 = FakeMessage(owner, "/cancel")
    await cancel_cmd(bot, m10)
    check("cancel clears state", OWNER_USER_ID not in auth.LOGIN_STATE)

    # 9. _do_sign_in robustness: never mixes positional + keyword, so the
    #    "got multiple values for argument 'phone_code_hash'" TypeError
    #    can never be raised - on ANY Pyrogram version/fork signature.
    class SigStandard:
        """Pyrogram 1.x & 2.x signature: (phone_number, phone_code_hash, phone_code)."""
        async def sign_in(self, phone_number, phone_code_hash, phone_code):
            return (phone_number, phone_code_hash, phone_code)

    class SigSwapped:
        """Hypothetical fork with a different parameter order."""
        async def sign_in(self, phone_number, phone_code, phone_code_hash):
            return (phone_number, phone_code_hash, phone_code)

    class SigKeywordsOnly:
        """Library that only accepts **kwargs (e.g. heavily patched)."""
        async def sign_in(self, **kwargs):
            return (kwargs.get("phone_number"), kwargs.get("phone_code_hash"), kwargs.get("phone_code"))

    for label, obj in (
        ("standard", SigStandard()),
        ("swapped order", SigSwapped()),
        ("keywords-only", SigKeywordsOnly()),
    ):
        try:
            res = await auth._do_sign_in(obj, "+989123456789", "HASH123", "12345")
            check(f"_do_sign_in works with {label} signature", res == ("+989123456789", "HASH123", "12345"))
        except Exception as exc:
            check(f"_do_sign_in works with {label} signature", False)
            print("   ->", type(exc).__name__, exc)

    # regression: the OLD buggy call style that caused the user's error
    # sign_in(phone, code, phone_code_hash=...) must NEVER be produced
    caught = []

    class Trap:
        async def sign_in(self, *args, **kwargs):
            caught.append((args, kwargs))

    await auth._do_sign_in(Trap(), "PH", "HASH", "CODE")
    args, kwargs = caught[0]
    check("no positional args passed to sign_in", args == ())
    check("phone_code_hash passed exactly once",
          sum(1 for v in [kwargs.get("phone_code_hash")] if v == "HASH") == 1
          and "HASH" not in args)
    check("code and number passed via kwargs",
          kwargs.get("phone_number") == "PH" and kwargs.get("phone_code") == "CODE")

    failed = [r for r in results if not r[1]]
    print("\n========================================")
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", [r[0] for r in failed])
        sys.exit(1)
    print("=== AUTH TEST PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
    os._exit(0 if all(r[1] for r in results) else 1)
