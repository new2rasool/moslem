"""مدل‌های پیام — واسط بین آداپتور تلگرام و هسته (مستقل از کتابخانه)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IncomingUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    is_bot: bool = False

    @property
    def name(self) -> str:
        full = (self.first_name or "") + (" " + self.last_name if self.last_name else "")
        return full.strip()


@dataclass
class IncomingChat:
    id: int
    title: str = ""
    is_private: bool = False


@dataclass
class IncomingMessage:
    id: int = 0
    chat: IncomingChat = field(default_factory=lambda: IncomingChat(0))
    user: IncomingUser | None = None
    text: str = ""
    content_type: str = ""          # photo/video/animation/document/…
    forwarded: bool = False         # هر نوع فوروارد (کاربر/کانال)
    forward_from_chat_id: int | None = None
    reply_to_message_id: int | None = None
    reply_to_user_id: int | None = None
    reply_to_user_name: str = ""
    service: str = ""               # new_members / left_member / …
    service_users: list[IncomingUser] = field(default_factory=list)
    service_user: IncomingUser | None = None


@dataclass
class IncomingCallback:
    id: str = ""
    data: str = ""
    chat: IncomingChat = field(default_factory=lambda: IncomingChat(0))
    user: IncomingUser | None = None
    message_id: int | None = None
