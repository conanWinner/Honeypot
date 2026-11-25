"""Voice adapter. Phase 2 will take a live call; this phase accepts a transcript segment."""

from app.channels.base import ChannelAdapter, InboundMessage


class VoiceChannel(ChannelAdapter):
    name = "voice"

    def parse(self, payload: dict) -> InboundMessage:
        text = (payload.get("transcript") or payload.get("text") or "").strip()
        if not text:
            raise ValueError("Bản ghi thoại trống.")
        return InboundMessage(
            channel=self.name,
            text=text,
            external_id=str(payload.get("segment_id") or ""),
            meta={"speaker": payload.get("speaker") or "remote"},
        )

    def render(self, text: str) -> dict:
        return {"channel": self.name, "text": text, "transport": "pending-voice"}
