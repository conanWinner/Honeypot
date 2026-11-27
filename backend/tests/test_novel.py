"""A scam that is not in the library, and a known one that must wait for review."""

import copy

from app.llm.mock import MockProvider
from app.models import Script
from app.services.matching import match_strength

NOVEL = [
    "Tôi gọi từ phòng CSGT, xe biển số của anh có biên bản phạt nguội vượt đèn đỏ.",
    "Anh phải nộp phạt trong hôm nay, quá hạn sẽ bị tước bằng lái và cưỡng chế.",
    "Anh vào đường dẫn csgt-phatnguoi.top để tra biên bản và nộp phạt online.",
    "Nếu không vào được link thì chuyển 1.250.000 vào số tài khoản 190366778899 Techcombank để nộp thay.",
]

KNOWN = [
    "Ví MoMo của bạn bị tạm khóa do đăng nhập lạ. Trong 15 phút không xác minh số dư sẽ phong tỏa.",
    "Bấm link để xác thực danh tính ví. Trang có logo MoMo.",
    "Nhập mã OTP MoMo vừa gửi để mở khóa. Không nhập là ví bị hủy.",
]


def _talk(client, persona_id: str, lines: list[str]) -> tuple[str, list[dict]]:
    created = client.post("/api/conversations", json={"persona_id": persona_id, "channel": "web"}).json()
    panels = []
    for line in lines:
        body = client.post(f"/api/conversations/{created['id']}/messages", json={"text": line})
        assert body.status_code == 200, body.text
        panels.append(body.json()["panel"])
    return created["id"], panels


def test_filler_turn_does_not_break_an_established_match():
    log = [
        {"family": "momo-khoa-vi", "score": 0.9},
        {"family": "hoc-phi-gia-truong", "score": 0.3},
        {"family": "evn-cat-dien", "score": 0.25},
    ]
    strength = match_strength(log)
    assert strength["weak"] is False
    assert strength["family"] == "momo-khoa-vi"


def test_drifting_weak_hits_stay_unmatched():
    log = [
        {"family": "hoc-phi-gia-truong", "score": 0.35},
        {"family": "buu-dien-ho-chieu", "score": 0.65},
        {"family": "khoa-hoc-thi-chung-chi", "score": 0.59},
    ]
    assert match_strength(log)["weak"] is True
    # Two moderate hits on one family establish it.
    log.append({"family": "khoa-hoc-thi-chung-chi", "score": 0.6})
    assert match_strength(log)["weak"] is False


def test_novel_scam_runs_on_general_playbook(client):
    seen: list[dict] = []

    class Spy(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            if schema.__name__ == "PlannerOutput":
                import json

                seen.append(json.loads(user.split("<<<CONTEXT>>>", 1)[1].split("<<<END>>>", 1)[0]))
            return super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)

    client.app.state.provider = Spy()
    try:
        _, panels = _talk(client, "ong-sau", NOVEL)
    finally:
        client.app.state.provider = MockProvider()
    assert all(panel["unmatched"] for panel in panels)
    assert panels[-1]["playbook"]["label"] == "Chung"
    assert seen and all(ctx.get("top_match") is None and ctx.get("unmatched") is True for ctx in seen)
    assert "190366778899" in "".join(panels[-1]["indicators"].get("bank_accounts") or [])


def test_novel_scam_is_filed_as_new_root(client):
    conversation_id, _ = _talk(client, "ong-sau", NOVEL)
    outcome = client.post(f"/api/conversations/{conversation_id}/extract").json()
    assert outcome["action"] == "queued"
    assert outcome["relation"] == "new_root"
    assert outcome["script"]["status"] == "pending"
    assert outcome["script"]["parent_id"] is None
    assert outcome["script"]["merge_target"] is None
    assert "Chưa khớp chắc" in outcome["script"]["novelty_note"]


def test_known_scam_waits_in_queue_before_merge(client, app):
    with app.state.Session() as session:
        target = session.get(Script, "momo-khoa-vi")
        before = {
            "occurrence_count": target.occurrence_count,
            "steps": copy.deepcopy(target.steps),
            "sources": copy.deepcopy(target.sources),
            "indicators": copy.deepcopy(target.indicators),
        }
    try:
        conversation_id, panels = _talk(client, "khoa-tx", KNOWN)
        assert not any(panel["unmatched"] for panel in panels)
        outcome = client.post(f"/api/conversations/{conversation_id}/extract").json()
        assert outcome["action"] == "queued"
        assert outcome["relation"] == "duplicate"
        pending = outcome["script"]
        assert pending["status"] == "pending"
        assert pending["merge_target"] == "momo-khoa-vi"
        assert pending["parent_id"] is None

        # Nothing touched the published script yet.
        unchanged = client.get("/api/scripts/momo-khoa-vi").json()
        assert unchanged["occurrence_count"] == before["occurrence_count"]

        queue = client.get("/api/moderation").json()
        row = next(item for item in queue if item["id"] == pending["id"])
        assert row["merge_target_title"]

        merged = client.post(f"/api/moderation/{pending['id']}/approve")
        assert merged.status_code == 200
        assert merged.json()["id"] == "momo-khoa-vi"
        assert merged.json()["occurrence_count"] == before["occurrence_count"] + 1
        with app.state.Session() as session:
            assert session.get(Script, pending["id"]).status == "merged"
    finally:
        with app.state.Session() as session:
            target = session.get(Script, "momo-khoa-vi")
            for key, value in before.items():
                setattr(target, key, value)
            session.commit()


def test_reviewer_can_publish_a_proposed_duplicate_as_its_own(client):
    conversation_id, _ = _talk(client, "khoa-tx", KNOWN)
    pending = client.post(f"/api/conversations/{conversation_id}/extract").json()["script"]
    published = client.post(f"/api/moderation/{pending['id']}/approve?mode=publish")
    assert published.status_code == 200
    body = published.json()
    assert body["id"] == pending["id"]
    assert body["status"] == "published"
    assert body["merge_target"] is None
    assert body["relation"] == "new_root"
    unchanged = client.get("/api/scripts/momo-khoa-vi").json()
    assert unchanged["occurrence_count"] >= 1
    # Leave the shared library as it was.
    with client.app.state.Session() as session:
        session.query(Script).filter(Script.id == pending["id"]).delete()
        session.commit()
