"""Live-model regressions: what made the persona sound scripted in a real run."""

import json

from app.llm.mock import MockProvider
from app.services.demo import DEMOS


def _ctx(user: str) -> dict:
    return json.loads(user.split("<<<CONTEXT>>>", 1)[1].split("<<<END>>>", 1)[0])


class ScamScoringAnalyst(MockProvider):
    """An analyst that reads scammer_suspicion as "how scammy", like the live model did,
    and a planner that keeps choosing confusion. Records what the persona was given."""

    def __init__(self):
        super().__init__()
        self.persona_ctx: list[dict] = []

    def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
        out = super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)
        name = schema.__name__
        if name == "AnalystOutput":
            out.scammer_suspicion = 0.95
        elif name == "PlannerOutput":
            out.goal = "feign_confusion"
        elif name == "PersonaOutput":
            self.persona_ctx.append(_ctx(user))
        return out


def _play(client, provider, demo_id):
    client.app.state.provider = provider
    try:
        started = client.post("/api/demo/start", params={"id": demo_id}).json()
        goals = []
        for line in DEMOS[demo_id]["lines"]:
            body = client.post(f"/api/conversations/{started['id']}/messages", json={"text": line}).json()
            goals.append(body["victim_message"]["reasoning"]["planner"]["goal"])
        return started["id"], goals
    finally:
        client.app.state.provider = MockProvider()


def test_scam_score_in_suspicion_field_does_not_freeze_the_agent(client):
    provider = ScamScoringAnalyst()
    _, goals = _play(client, provider, "moi-phat-nguoi-ong-sau")
    # The account is read back and a second way to pay is asked for, as on mock.
    assert "confirm_account" in goals
    assert "ask_alternative" in goals
    # Never three turns of confusion or stalling in a row.
    soft = {"feign_confusion", "stall"}
    assert not any(set(goals[i : i + 3]) <= soft for i in range(len(goals) - 2)), goals


def test_persona_sees_the_dialogue_and_is_told_to_stop_asking(client):
    provider = ScamScoringAnalyst()
    _play(client, provider, "moi-phat-nguoi-ong-sau")
    last = provider.persona_ctx[-1]
    assert [row["who"] for row in last["recent_dialogue"]][-1] == "họ"
    assert last["recent_dialogue"][-1]["text"] == DEMOS["moi-phat-nguoi-ong-sau"]["lines"][-1]
    assert len(last["recent_dialogue"]) == 6
    assert {row["who"] for row in last["recent_dialogue"]} == {"họ", "mình"}


def test_identity_from_self_introduction_is_not_asked_again(client):
    from app.agent.casefile import harvest_indicators

    assert harvest_indicators("Tôi gọi từ phòng CSGT, xe máy biển số của chú có biên bản.")["who"] == "phòng CSGT"
    assert harvest_indicators("Chào anh Khoa, em bên trung tâm sát hạch lái xe.")["who"] == "trung tâm sát hạch lái xe"


def test_doubt_needs_a_cue_in_the_message():
    from app.agent.policy import doubt_cue

    assert doubt_cue("Sao chú hỏi nhiều thế, có phải người thật không?")
    assert doubt_cue("Bác trả lời lạ quá")
    assert not doubt_cue("Chú phải nộp phạt trong hôm nay, quá hạn sẽ bị tước bằng lái.")
    assert not doubt_cue("Chuyện này chú không được kể với ai.")
    assert not doubt_cue("Xe máy biển số của chú có biên bản phạt nguội.")
    assert doubt_cue("Bác là AI à?")


def test_same_exclamation_is_not_repeated():
    from app.agent.policy import drop_repeated_interjection as drop

    recent = ["Dạ thật ạ?", "Ôi bé Bông nhà em dưới 6 tuổi ạ."]
    assert drop("Ôi em chưa kịp đăng ký ạ, hạn tới ngày nào?", recent) == "Em chưa kịp đăng ký ạ, hạn tới ngày nào?"
    assert drop("Dạ em ghi lại nha", ["Dạ thật ạ?"]) == "Dạ em ghi lại nha"
    assert drop("Ôi thế à", ["Ơ"]) == "Ôi thế à"
    assert drop("Ơ, chú không rành.", ["Ơ hay, xe chú để ở nhà."]) == "Chú không rành."
