"""
زمینه‌های (Context) اجرا — اشیای مستقل از ترنسپورت که به دستورهای پلاگین داده می‌شوند.

هر هندلر فقط یک Context می‌گیرد و با ctx.respond(...) پیام می‌فرستد؛ این‌که پیام در
تلگرام ارسال شود یا در تست جمع شود، به «آداپتور» واگذار می‌شود (جداسازی کامل از تلگرام).
"""

from __future__ import annotations

from dataclasses import dataclass, field


class _Sender:
    """مجموعه‌کنندهٔ پیام‌های خروجی (آداپتور بعد از هندلر آن‌ها را می‌فرستد)."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.keyboards: list[list[list[dict]]] = []

    def respond(self, text: str) -> None:
        if text:
            self.messages.append(text)

    def respond_buttons(self, text: str, buttons: list[list[dict]]) -> None:
        """پیام + صفحه‌کلید شیشه‌ای (آداپتور دکمه‌ها را می‌سازد؛ داده به callback می‌رود)."""
        if text:
            self.messages.append(text)
        self.keyboards.append(buttons or [])


def _act(actions: list[dict], kind: str, **kw) -> None:
    """ثبت یک «اکشن ساختاریافته» (اجرای فیزیکی با آداپتور)."""
    actions.append({"type": kind, **kw})


@dataclass
class CommandContext:
    """زمینهٔ یک فرمان اجراشده.

    chat_id برای پیام خصوصی None است.
    """

    plugin: str
    command: str
    args: str
    raw_text: str
    user_id: int
    chat_id: int | None = None
    is_private: bool = False
    lang: str = "fa"
    sender_name: str = ""
    sender_username: str = ""
    reply_to_user_id: int | None = None
    reply_to_user_name: str = ""
    actions: list = field(default_factory=list)
    keyboards: list = field(default_factory=list)
    _sender: _Sender = field(default_factory=_Sender, repr=False)

    def respond(self, text: str) -> None:
        """افزودن پیام خروجی (پاسخ به فرمان)."""
        self._sender.respond(text)

    def respond_buttons(self, text: str, buttons: list[list[dict]]) -> None:
        """پیام + دکمه‌های شیشه‌ای (دادهٔ هر دکمه برای callback استفاده می‌شود)."""
        self.respond(text)
        self.keyboards.append(buttons or [])

    def act(self, kind: str, **kw) -> None:
        """درخواست یک اکشن فیزیکی از آداپتور (مثل delete/restrict/ban)."""
        _act(self.actions, kind, **kw)

    @property
    def outgoing(self) -> list[str]:
        return self._sender.messages


@dataclass
class EventContext:
    """زمینهٔ یک رویداد (مثل پیوستن عضو) برای پخش بین پلاگین‌ها."""

    kind: str
    chat_id: int | None
    lang: str = "fa"
    user_id: int | None = None
    user_name: str = ""
    user_username: str = ""
    data: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    keyboards: list = field(default_factory=list)
    _sender: _Sender = field(default_factory=_Sender, repr=False)

    def respond(self, text: str) -> None:
        self._sender.respond(text)

    def respond_buttons(self, text: str, buttons: list[list[dict]]) -> None:
        self.respond(text)
        self.keyboards.append(buttons or [])

    def act(self, kind: str, **kw) -> None:
        """درخواست یک اکشن فیزیکی از آداپتور (مثل delete_message/restrict)."""
        _act(self.actions, kind, **kw)

    @property
    def outgoing(self) -> list[str]:
        return self._sender.messages


@dataclass
class CallbackContext:
    """زمینهٔ کلیک روی دکمهٔ شیشه‌ای (inline callback)."""

    plugin: str
    prefix: str
    action: str          # بخشی که پلاگین خودش تعریف می‌کند (مثلاً "approve")
    payload: str         # دادهٔ خام پس از prefix
    raw_action: str      # کل اکشن (prefix + action + payload)
    user_id: int
    chat_id: int | None = None
    lang: str = "fa"
    actions: list = field(default_factory=list)
    keyboards: list = field(default_factory=list)
    _sender: _Sender = field(default_factory=_Sender, repr=False)

    def respond(self, text: str) -> None:
        self._sender.respond(text)

    def respond_buttons(self, text: str, buttons: list[list[dict]]) -> None:
        self.respond(text)
        self.keyboards.append(buttons or [])

    def act(self, kind: str, **kw) -> None:
        _act(self.actions, kind, **kw)

    @property
    def outgoing(self) -> list[str]:
        return self._sender.messages
