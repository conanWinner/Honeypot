"""Persona text should read like a person texting. See app/agent/humanize.py for sources."""

import re

import pytest

from app.agent.humanize import ai_tells, humanize, typing_delay_ms
from app.agent.policy import inspect_outbound, voice_issues
from app.data.personas import PERSONAS, PRONOUNS, STYLES
from app.llm.mock_lines import LINES

FILL = {"{otp}": "482913", "{hook}": "sổ tiết kiệm", "{account}": "9704229912345", "{bank}": "Vietcombank"}
ALLOWED = {"482913", "9704229912345"}


def _render(line: str) -> str:
    for key, value in FILL.items():
        line = line.replace(key, value)
    return line


def _all_lines():
    for slug, goals in LINES.items():
        for goal, lines in goals.items():
            for line in lines:
                yield slug, goal, _render(line)


def test_every_persona_has_styles_and_lines():
    ids = {persona["id"] for persona in PERSONAS}
    assert ids == set(STYLES) == set(LINES)
    goals = set(LINES["tuan-vp"])
    for slug in ids:
        assert set(LINES[slug]) == goals, slug


@pytest.mark.parametrize("slug,goal,line", list(_all_lines()))
def test_mock_line_is_safe_in_voice_and_human(slug, goal, line):
    assert inspect_outbound(line, ALLOWED, slug) == [], line
    assert voice_issues(line, slug) == [], line
    assert ai_tells(line, [], slug) == [], line
    if goal == "read_fake_otp":
        assert "482913" in line
    if goal == "confirm_account":
        assert "9704229912345" in line


def test_mock_lines_rarely_say_not_paid():
    """The old lines said "chưa chuyển" in almost every message."""
    lines = [line for _, _, line in _all_lines()]
    said = [line for line in lines if re.search(r"chưa\s+(chuyển|ck)", line, re.IGNORECASE)]
    assert len(said) / len(lines) < 0.05


def test_tells_are_detected():
    assert "slash_address" in ai_tells("Anh/chị gửi lại link giúp em.", [], "tuan-vp")
    assert "formal_phrase" in ai_tells("Ngoài ra, vui lòng gửi thêm thông tin.", [], "tuan-vp")
    assert "desk_words" in ai_tells("Cô chưa thực hiện thao tác nào.", [], "ba-nam")
    assert "desk_words" not in ai_tells("Em chưa thực hiện thao tác nào.", [], "tuan-vp")
    assert "too_long" in ai_tells("x " * 60, [], "khoa-tx")
    assert "repeated_disclaimer" in ai_tells("Em chưa chuyển đâu.", ["em chưa ck"], "tuan-vp")
    assert "too_tidy" in ai_tells("Link đâu anh gửi lại.", [], "minh-sv")
    assert "question_wall" in ai_tells("Ai vậy? Để làm gì? Chuyển cho ai?", [], "tuan-vp", incoming="Anh chuyển chưa?")
    assert ai_tells("ơ link đâu anh", [], "minh-sv") == []


def test_humanize_picks_one_address_word():
    assert humanize("Anh/chị gửi lại link giúp em.", "tuan-vp") == "Anh gửi lại link giúp em."
    assert "/" not in humanize("Cháu/anh nói lại xem.", "ong-sau")


def test_humanize_drops_a_repeated_standalone_disclaimer_only():
    recent = ["Số tài khoản nào? Em chưa chuyển."]
    assert humanize("Link đâu anh? Em chưa chuyển đâu.", "tuan-vp", recent) == "Link đâu anh?"
    # Not repeated recently: kept.
    assert "chưa chuyển" in humanize("Link đâu anh? Em chưa chuyển đâu.", "tuan-vp", [])
    # Part of a real question: kept.
    kept = humanize("Em chưa chuyển, tiền này đưa cho ai vậy anh?", "tuan-vp", recent)
    assert "chưa chuyển" in kept
    # Never empties a reply.
    assert humanize("Em chưa chuyển đâu.", "tuan-vp", recent)


def test_humanize_types_like_the_persona():
    out = humanize("Không được rồi anh. Gửi lại link đi.", "minh-sv", seed="a")
    assert out[0].islower() and not out.endswith(".")
    marked = [humanize("Cái link ấy cháu gửi lại xem.", "ong-sau", seed=f"conv{i}:1") for i in range(40)]
    plain = [line for line in marked if line.startswith("Cai link ay chau")]
    assert 0 < len(plain) < len(marked)
    # Same conversation, every turn: one keyboard habit throughout.
    lines = ["Cái link ấy cháu gửi lại xem.", "Số tài khoản là số nào.", "Thế là chuyện gì hả cháu."]
    for conv in ("a", "b", "c", "d", "e"):
        from app.agent.humanize import _strip_marks

        outs = [humanize(line, "ong-sau", seed=f"{conv}:{turn}") for turn, line in enumerate(lines)]
        styles = {out == _strip_marks(out) for out in outs}
        assert len(styles) == 1, conv


@pytest.mark.parametrize("slug", sorted(STYLES))
def test_humanize_never_adds_violations_or_changes_digits(slug):
    for _, _, line in _all_lines():
        for seed in ("1", "2", "3"):
            out = humanize(line, slug, ["Em chưa chuyển."], seed=seed)
            assert re.findall(r"\d+", out) == re.findall(r"\d+", line)
            assert set(inspect_outbound(out, ALLOWED, slug)) <= set(inspect_outbound(line, ALLOWED, slug)) | {"pronoun_mix"}
            assert out.strip()


def test_typing_delay_follows_persona_speed():
    reply = "Cái link ấy cháu gửi lại xem, chú không thấy."
    slow = typing_delay_ms(reply, "Bấm vào link", "ong-sau", "x")
    fast = typing_delay_ms(reply, "Bấm vào link", "khoa-tx", "x")
    assert slow > fast
    assert 1200 <= fast <= 9000 and 1200 <= slow <= 9000
    assert typing_delay_ms("ok", "", "khoa-tx", "x") < typing_delay_ms(reply * 2, "", "khoa-tx", "x")


def test_persona_gets_style_and_not_every_reply_disclaims(client):
    import json

    from app.llm.mock import MockProvider

    seen = []

    class Spy(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            if schema.__name__ == "PersonaOutput":
                seen.append(json.loads(user.split("<<<CONTEXT>>>", 1)[1].split("<<<END>>>", 1)[0]))
            return super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)

    client.app.state.provider = Spy()
    try:
        created = client.post("/api/conversations", json={"persona_id": "lan-nt"}).json()
        replies = []
        for line in [
            "Chị ơi đơn hàng của chị bị hoàn, phải đóng phí 30 nghìn.",
            "Chị chuyển phí nhanh giúp em.",
            "Nhanh lên chị, quá giờ là hủy đơn.",
            "Chị chuyển chưa?",
        ]:
            body = client.post(f"/api/conversations/{created['id']}/messages", json={"text": line}).json()
            replies.append(body["victim_message"]["content"])
    finally:
        client.app.state.provider = MockProvider()
    assert seen and seen[0]["style"]["max_chars"] == STYLES["lan-nt"]["max_chars"]
    said = [reply for reply in replies if re.search(r"chưa\s+(chuyển|ck)", reply, re.IGNORECASE)]
    assert len(said) <= 1, replies
    for reply in replies:
        assert "/" not in reply
        assert voice_issues(reply, "lan-nt") == [], reply
        assert PRONOUNS["lan-nt"]["self"][0] in reply.lower() or len(reply) < 40, reply


@pytest.mark.parametrize(
    "text,probe",
    [
        ("Chú có phải máy không đấy? Sao trả lời lạ vậy.", True),
        ("em là bot à", True),
        ("Anh có phải người thật không", True),
        ("sao trả lời lạ thế", True),
        ("Chị là AI hả", True),
        ("Chú là ai mà hỏi nhiều", False),
        ("Cháu là ai?", False),
        ("ai đứng tên tài khoản này", False),
        ("máy chú bị lỗi à", False),
        ("đây là tin nhắn tự động của ngân hàng", False),
    ],
)
def test_bot_probe_in_any_address_form(text, probe):
    from app.agent.policy import assess_inbound

    assert assess_inbound(text)["scammer_suspicious"] is probe


def test_persona_answers_a_bot_probe_instead_of_ignoring_it(client):
    created = client.post("/api/conversations", json={"persona_id": "ong-sau"}).json()
    client.post(f"/api/conversations/{created['id']}/messages", json={"text": "Chú ơi, hồ sơ cư trú của chú bị sai, phải nộp phí 200 nghìn."})
    body = client.post(
        f"/api/conversations/{created['id']}/messages", json={"text": "Chú có phải máy không đấy? Sao trả lời lạ vậy."}
    ).json()
    assert body["panel"]["goal"]["goal"] in {"feign_confusion", "stall", "emotional_hook"}
    reply = body["victim_message"]["content"].lower()
    assert "link" not in reply and "tài khoản" not in reply


def test_humanize_never_stacks_dots():
    for seed in map(str, range(30)):
        out = humanize("Có số hiệu không, cô hỏi cho chắc nhé...", "ba-nam", seed=seed)
        assert "...." not in out
        assert humanize("Thế à..... cháu nói đi", "ong-sau", seed=seed).count(".") <= 3


def test_age_shapes_typing():
    from app.agent.humanize import humanize
    from app.agent.textutil import fold

    elder = "Chú ghi số 190366778899 nhé, đúng chưa cháu? Không biết chuyển khoản đâu."
    young = "Dạ anh ơi, em không biết chuyển khoản như thế nào, phải chuyển bao nhiêu vậy anh?"
    elder_out = [humanize(elder, "ong-sau", [], seed=f"c{i}:3") for i in range(12)]
    young_out = [humanize(young, "minh-sv", [], seed=f"c{i}:3") for i in range(12)]
    # The account number survives every rewrite.
    assert all("190366778899" in out for out in elder_out)
    # Older people drop marks in most chats but spell words out.
    assert sum(out.isascii() for out in elder_out) >= 6
    assert all("ck" not in out.split() and "ko" not in out.split() for out in elder_out)
    # Young people shorten words in most messages, and the meaning words stay.
    shortened = [out for out in young_out if {"ko", "e", "a", "bt", "ck", "bn", "z", "ntn"} & set(out.replace(",", " ").replace("?", " ").split())]
    assert len(shortened) >= 9
    assert all(out[0].islower() for out in young_out)
