"""Simulation engine: redaction, scoring, end conditions, mock mode, quiz safety."""

import json

from app.models import Script
from app.services.training import sanitize_scammer_text, scammer_text_safe


def _session(client, **body):
    response = client.post("/api/training/sessions", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _say(client, session_id, text):
    response = client.post(f"/api/training/sessions/{session_id}/messages", json={"text": text})
    return response


def test_sanitize_examples():
    account = sanitize_scammer_text("chuyển vào 0123456789 vietcombank chủ tài khoản nguyễn văn hùng")
    assert "nguyễn văn hùng" not in account.lower()
    assert "0123456789" not in account
    assert not any(len(run) >= 7 for run in __import__("re").findall(r"\d+", account))

    link = sanitize_scammer_text("vào link https://abc-xyz.top/login")
    assert "[LINK_GIẢ]" in link
    assert "abc-xyz.top" not in link
    assert "http" not in link

    apk = sanitize_scammer_text("tải file dichvucong.apk")
    assert "[APP_GIẢ]" in apk
    assert ".apk" not in apk.lower()

    remote = sanitize_scammer_text("ID ultraview 123 456 789")
    assert "[ID_GIẢ]" in remote
    assert "123" not in remote

    same = "chuyển 5 triệu trong 15 phút"
    assert sanitize_scammer_text(same) == same
    assert scammer_text_safe(same)


def test_scenarios_cover_published_library(client):
    payload = client.get("/api/training/scenarios").json()
    assert len(payload["groups"]) >= 9
    assert len(payload["scenarios"]) >= 30
    assert {item["id"] for item in payload["groups"]} >= {
        "cong-an",
        "ngan-hang-vi",
        "giao-hang",
        "viec-lam",
        "dau-tu",
        "qr",
        "deepfake-nguoi-than",
        "cai-app",
        "khac",
    }
    with client.app.state.Session() as session:
        published = {row.id for row in session.query(Script).filter(Script.status == "published")}
        pending = {row.id for row in session.query(Script).filter(Script.status != "published")}
    ids = {item["script_id"] for item in payload["scenarios"]}
    assert ids <= published
    assert not ids & pending


def test_create_session_with_and_without_script(client):
    listed = client.get("/api/training/scenarios").json()["scenarios"]
    script_id = listed[0]["script_id"]
    chosen = _session(client, script_id=script_id, difficulty="vua", mode="thu_thach")
    assert chosen["status"] == "active"
    assert chosen["messages"][0]["role"] == "scammer"
    assert chosen["messages"][0]["text"]
    assert scammer_text_safe(chosen["messages"][0]["text"])
    random_one = _session(client, difficulty="de", mode="hoc")
    assert random_one["status"] == "active"
    assert random_one["messages"][0]["role"] == "scammer"


def test_safe_path_scores_and_catches_a_flag(client):
    created = _session(client)
    first = _say(client, created["id"], "Anh là ai, tôi sẽ gọi lên công an phường để xác minh")
    assert first.status_code == 200, first.text
    assert first.json()["session"]["status"] == "active"
    second = _say(client, created["id"], "Tôi không chuyển, tôi gác máy")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["session"]["status"] == "safe"
    debrief = client.get(f"/api/training/sessions/{created['id']}/debrief")
    assert debrief.status_code == 200, debrief.text
    report = debrief.json()
    assert report["score"] >= 70
    assert any(stage["outcome"] == "caught" for stage in report["stages"])


def test_otp_is_masked_and_scores_as_scammed(client):
    created = _session(client)
    response = _say(client, created["id"], "Mã OTP của tôi là 482913")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session"]["status"] == "scammed"
    stored = " ".join(message["text"] for message in body["session"]["messages"] if message["role"] == "user")
    assert "[ĐÃ CHE]" in stored
    assert "482913" not in stored
    assert "482913" not in json.dumps(body)
    report = client.get(f"/api/training/sessions/{created['id']}/debrief").json()
    assert report["score"] <= 30


def test_actions_end_the_session(client):
    scammed = _session(client)
    fell = client.post(f"/api/training/sessions/{scammed['id']}/action", json={"action": "share_otp"})
    assert fell.status_code == 200
    assert fell.json()["status"] == "scammed"
    safe = _session(client)
    hung = client.post(f"/api/training/sessions/{safe['id']}/action", json={"action": "hang_up"})
    assert hung.status_code == 200
    assert hung.json()["status"] == "safe"


def test_closed_session_conflicts_and_unknown_is_missing(client):
    created = _session(client)
    client.post(f"/api/training/sessions/{created['id']}/action", json={"action": "hang_up"})
    again = _say(client, created["id"], "alo")
    assert again.status_code == 409
    missing = client.get("/api/training/sessions/does-not-exist")
    assert missing.status_code == 404
    assert "Không thấy" in missing.json()["detail"]


def test_turn_limit_times_out(client):
    created = _session(client, difficulty="vua")
    status = "active"
    for _ in range(20):
        response = _say(client, created["id"], "ừ")
        assert response.status_code == 200, response.text
        status = response.json()["session"]["status"]
        if status != "active":
            break
    assert status == "timeout"
    report = client.get(f"/api/training/sessions/{created['id']}/debrief").json()
    assert report["score"] <= 70


def test_hint_costs_five_points(client):
    listed = client.get("/api/training/scenarios").json()["scenarios"]
    script_id = listed[0]["script_id"]
    hinted = _session(client, script_id=script_id)
    plain = _session(client, script_id=script_id)
    hint = client.post(f"/api/training/sessions/{hinted['id']}/hint")
    assert hint.status_code == 200
    assert hint.json()["hints_used"] == 1
    assert hint.json()["hint"]
    client.post(f"/api/training/sessions/{hinted['id']}/action", json={"action": "hang_up"})
    client.post(f"/api/training/sessions/{plain['id']}/action", json={"action": "hang_up"})
    left = client.get(f"/api/training/sessions/{hinted['id']}/debrief").json()["score"]
    right = client.get(f"/api/training/sessions/{plain['id']}/debrief").json()["score"]
    assert left == right - 5


def test_every_published_script_stays_safe_in_mock(client):
    scenarios = client.get("/api/training/scenarios").json()["scenarios"]
    before = None
    with client.app.state.Session() as session:
        before = session.query(Script).count()
    for item in scenarios:
        created = _session(client, script_id=item["script_id"], difficulty="de")
        status = created["status"]
        guard = 0
        while status == "active" and guard < 16:
            response = _say(client, created["id"], "ừ")
            assert response.status_code == 200, response.text
            status = response.json()["session"]["status"]
            guard += 1
        assert status != "active"
        stored = client.get(f"/api/training/sessions/{created['id']}").json()
        for message in stored["messages"]:
            if message["role"] == "scammer":
                assert scammer_text_safe(message["text"]), message["text"]
    with client.app.state.Session() as session:
        assert session.query(Script).count() == before


def test_quiz_mixes_answers_and_stays_safe(client):
    payload = client.get("/api/training/quiz", params={"n": 8}).json()
    assert len(payload["questions"]) == 8
    answers = {item["answer"] for item in payload["questions"]}
    assert answers == {"scam", "safe"}
    for item in payload["questions"]:
        assert scammer_text_safe(item["text"]), item["text"]


def test_simulation_uses_only_sim_and_analyst(client):
    calls = []
    provider = client.app.state.provider
    original = provider.complete

    def wrapped(*args, **kwargs):
        calls.append(kwargs.get("role") or "")
        return original(*args, **kwargs)

    provider.complete = wrapped
    try:
        created = _session(client)
        assert calls == []
        response = _say(client, created["id"], "ừ")
        assert response.status_code == 200
        assert calls
        assert set(calls) <= {"sim", "analyst"}
    finally:
        provider.complete = original
