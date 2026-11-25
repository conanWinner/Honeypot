"""Channel boundary. The agent sees text. Transports stay outside the loop."""

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    channel: str
    text: str
    external_id: str = ""
    meta: dict = Field(default_factory=dict)


class ChannelAdapter:
    name = "base"

    def parse(self, payload: dict) -> InboundMessage:
        raise NotImplementedError

    def render(self, text: str) -> dict:
        return {"channel": self.name, "text": text}
