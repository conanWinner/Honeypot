from app.channels.base import ChannelAdapter, InboundMessage


class WebChannel(ChannelAdapter):
    name = "web"

    def parse(self, payload: dict) -> InboundMessage:
        text = (payload.get("text") or "").strip()
        if not text:
            raise ValueError("Tin nhắn trống.")
        return InboundMessage(channel=self.name, text=text, external_id=str(payload.get("external_id") or ""))
