"""Telegram adapter.

Phase 2 will attach Telethon and run MTProto on the user's own account.
This phase only normalizes an already-decoded message so the agent does not change.
"""

from app.channels.base import ChannelAdapter, InboundMessage


class TelegramChannel(ChannelAdapter):
    name = "telegram"

    def parse(self, payload: dict) -> InboundMessage:
        text = (payload.get("text") or payload.get("message") or "").strip()
        if not text:
            raise ValueError("Tin nhắn Telegram trống.")
        return InboundMessage(
            channel=self.name,
            text=text,
            external_id=str(payload.get("message_id") or payload.get("external_id") or ""),
            meta={"chat_id": payload.get("chat_id")},
        )

    def render(self, text: str) -> dict:
        return {"channel": self.name, "text": text, "transport": "pending-telethon"}

    def connect_userbot(self) -> None:
        raise NotImplementedError(
            "Kết nối Telethon (MTProto trên chính tài khoản người dùng) là pha 2, chưa bật trong bản web."
        )
