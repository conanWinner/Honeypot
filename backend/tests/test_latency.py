"""Skipping the guard model on plain lines must never skip it on a risky one."""

import re

import pytest

from app.agent.policy import guard_skippable, inspect_outbound
from app.agent.prompts import SAFETY_SYSTEM
from app.llm.mock_lines import LINES

# Every "block" and "allow" example the guard prompt teaches, plus the claims the
# rules are built around. None of them may skip the guard.
PROMPT_EXAMPLES = re.findall(r'Ví dụ[^:]*:\s*"([^"]+)"', SAFETY_SYSTEM)
RISKY = PROMPT_EXAMPLES + [
    "Anh bảo gì em cũng làm, em chờ lệnh.",
    "Cài cái phần mềm điều khiển xong rồi, giờ mở mục nào?",
    "Mình quét cái mã thanh toán xong rồi.",
    "Em làm đúng những gì anh dặn rồi.",
    "Cô gửi ảnh căn cước cho cháu nhé.",
    "Em là AI thôi mà.",
    "Mình là bot à?",
    "Ok để em chuyển liền.",
    "Mật khẩu là gì anh?",
    "Em nhấn vào rồi.",
    "Số của em là 0912000111.",
]
PLAIN = [
    "Ôi, cháu tên gì, ở công an phường nào? Có số hiệu không?",
    "Ai đấy? Cô không lưu số này.",
    "ủa có chuyện gì vậy anh",
    "Đợi chú tí, để chú tìm cái kính.",
    "Rồi sao nữa?",
    "Cái gì cơ, nói lại xem nào.",
]


def test_prompt_examples_were_found():
    assert len(PROMPT_EXAMPLES) >= 8


@pytest.mark.parametrize("line", RISKY)
def test_risky_lines_always_reach_the_guard(line):
    assert not guard_skippable(line, [])


@pytest.mark.parametrize("line", PLAIN)
def test_plain_lines_skip_the_guard(line):
    assert guard_skippable(line, [])


def test_rule_violation_or_length_keeps_the_guard():
    assert not guard_skippable("Ai đấy?", ["pronoun_mix"])
    assert not guard_skippable("Ai đấy? " * 30, [])
    # A number the scammer gave may be read back; any other number goes to the guard.
    assert not guard_skippable("Số 0451000123987 đúng không cháu?", [], set())


def _render(line: str) -> str:
    return line.replace("{otp}", "482913").replace("{account}", "0451000123987").replace("{bank}", "Vietcombank").replace("{hook}", "sổ tiết kiệm")


def test_no_mock_line_that_mentions_money_or_codes_skips():
    for persona, goals in LINES.items():
        for goal, lines in goals.items():
            if goal not in {"read_fake_otp", "ask_account_number", "ask_link", "ask_remote_id", "ask_alternative", "ask_transfer_destination"}:
                continue
            for line in map(_render, lines):
                assert not guard_skippable(line, inspect_outbound(line, {"482913"}, persona), {"482913"}, goal), (persona, goal, line)


def test_read_back_of_the_scammers_own_number_may_skip():
    line = _render(LINES["ba-nam"]["confirm_account"][0])
    assert guard_skippable(line, [], {"0451000123987"})
    assert not guard_skippable(line, [], set())


# --- A slow analyst does not hold the turn -------------------------------------

import time

from app.llm.mock import MockProvider


def _slow_analyst(analyst_s: float, persona_s: float = 0.0, grace: float = 0.2):
    class Slow(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            out = super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)
            if schema.__name__ == "AnalystOutput":
                time.sleep(analyst_s)
                return out.model_copy(update={"extracted_fact": "FACT-FROM-SLOW-ANALYST"})
            if schema.__name__ == "PersonaOutput":
                time.sleep(persona_s)
            return out

    provider = Slow()
    provider.analyst_grace = grace
    return provider


def _one_turn(client, provider):
    client.app.state.provider = provider
    try:
        created = client.post("/api/conversations", json={"persona_id": "tuan-vp"}).json()
        started = time.perf_counter()
        body = client.post(
            f"/api/conversations/{created['id']}/messages",
            json={"text": "Em bên ngân hàng, tài khoản của anh bị trừ phí bảo hiểm, muốn hủy phải đóng phí."},
        ).json()
        return time.perf_counter() - started, body, created["id"]
    finally:
        client.app.state.provider = MockProvider()


def test_slow_analyst_does_not_hold_the_turn(client):
    elapsed, body, _ = _one_turn(client, _slow_analyst(2.0))
    assert elapsed < 1.5
    assert body["panel"]["analyst_status"] == "late"
    assert body["panel"]["goal"]["goal"]
    assert body["victim_message"]["content"]


def test_late_analyst_is_merged_when_it_arrives_before_saving(client, app):
    from app.models import Conversation

    _, body, conversation_id = _one_turn(client, _slow_analyst(0.6, persona_s=1.0))
    assert body["panel"]["analyst_status"] == "late_merged"
    assert body["panel"]["extracted_fact"] == "FACT-FROM-SLOW-ANALYST"
    with app.state.Session() as session:
        state = session.get(Conversation, conversation_id).state
    assert "FACT-FROM-SLOW-ANALYST" in state["extracted_facts"]


def test_zero_grace_waits_for_the_analyst(client):
    elapsed, body, _ = _one_turn(client, _slow_analyst(1.2, grace=0))
    assert elapsed >= 1.2
    assert body["panel"]["analyst_status"] == "on_time"
    assert body["panel"]["extracted_fact"] == "FACT-FROM-SLOW-ANALYST"
