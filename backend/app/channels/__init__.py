from app.channels.telegram import TelegramChannel
from app.channels.voice import VoiceChannel
from app.channels.web import WebChannel

ADAPTERS = {
    "web": WebChannel(),
    "telegram": TelegramChannel(),
    "voice": VoiceChannel(),
}


def get_adapter(name: str):
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError("Kênh không hỗ trợ.") from exc
