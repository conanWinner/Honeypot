import pytest

from app.channels import get_adapter
from app.channels.telegram import TelegramChannel
from app.channels.voice import VoiceChannel


def test_telegram_and_voice_normalize_text():
    telegram = get_adapter("telegram").parse({"message": "Chuyển tiền gấp", "message_id": 12, "chat_id": 99})
    assert telegram.channel == "telegram"
    assert telegram.text == "Chuyển tiền gấp"
    assert telegram.external_id == "12"
    voice = VoiceChannel().parse({"transcript": "Đây là công an", "segment_id": "s1"})
    assert voice.channel == "voice"
    assert "công an" in voice.text


def test_telegram_userbot_is_not_wired():
    with pytest.raises(NotImplementedError):
        TelegramChannel().connect_userbot()


def test_unknown_channel():
    with pytest.raises(ValueError):
        get_adapter("sms-radio")
