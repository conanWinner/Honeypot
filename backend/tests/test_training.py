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
    assert sum(1 for item in payload["questions"] if item["answer"] == "scam") == 5
    for item in payload["questions"]:
        assert scammer_text_safe(item["text"]), item["text"]
        assert 2 <= len(item["lines"]) <= 5
        assert 2 <= len(item["flags"]) <= 3
        assert item["explain"] and item["action"] and item["context"] and item["sender"]


def test_quiz_bank_is_static_and_clean(client):
    from app.data.quiz_bank import QUIZ_BANK
    from app.data.warnings import BY_ID

    assert 10 <= len(QUIZ_BANK) <= 12
    scam = [item for item in QUIZ_BANK if item["answer"] == "scam"]
    safe = [item for item in QUIZ_BANK if item["answer"] == "safe"]
    assert scam and safe
    assert abs(len(scam) / len(QUIZ_BANK) - 0.6) <= 0.15
    with client.app.state.Session() as session:
        published = {row.id for row in session.query(Script).filter(Script.status == "published")}
    for item in QUIZ_BANK:
        assert 2 <= len(item["lines"]) <= 5
        assert 2 <= len(item["flags"]) <= 3
        assert len(item["explain"].split(".")) >= 2
        assert item["action"] and item["context"] and item["sender"]
        blob = " ".join(
            [item["context"], item["sender"], item["sender_detail"], item["action"], item["explain"], *item["lines"], *item["flags"]]
        )
        assert scammer_text_safe(blob), item["id"]
        joined = " ".join(item["lines"])
        for phrase in item["highlights"]:
            assert phrase in joined
        if item["script_id"]:
            assert item["script_id"] in published
        if item["warning_id"]:
            assert item["warning_id"] in BY_ID


def test_raw_secrets_are_judged_then_masked(client):
    """The UI posts the original line. The server scores that line, then stores it masked."""
    otp = _session(client)
    otp_response = _say(client, otp["id"], "Mã OTP của tôi là 482913")
    assert otp_response.json()["session"]["status"] == "scammed"
    assert otp_response.json()["judgment"]["label"] == "fell"

    password = _session(client)
    hidden = _say(client, password["id"], "mật khẩu của tôi là secret123")
    assert hidden.status_code == 200, hidden.text
    body = hidden.json()
    assert body["session"]["status"] == "scammed"
    stored = " ".join(message["text"] for message in body["session"]["messages"] if message["role"] == "user")
    assert "secret123" not in stored
    assert "[ĐÃ CHE]" in stored

    spaced = _session(client)
    leaked = _say(client, spaced["id"], "căn cước của tôi là 079 203 001 234 và sđt 0901234567")
    assert leaked.json()["session"]["status"] == "scammed"
    saved = " ".join(message["text"] for message in leaked.json()["session"]["messages"] if message["role"] == "user")
    assert "079" not in saved
    assert "0901234567" not in saved
    assert "[ĐÃ CHE]" in saved


def test_negation_and_questions_do_not_count_as_a_fall(client):
    refused = _say(client, _session(client)["id"], "tôi không chuyển rồi")
    assert refused.json()["session"]["status"] == "active"
    assert refused.json()["judgment"]["label"] == "refuse"

    report = _say(client, _session(client)["id"], "tôi không báo công an")
    assert report.json()["session"]["status"] == "active"
    assert report.json()["judgment"]["label"] != "fell"

    question = _say(client, _session(client)["id"], "mật khẩu là gì")
    assert question.json()["session"]["status"] == "active"
    assert question.json()["judgment"]["label"] != "fell"
    assert "gì" in question.json()["session"]["messages"][-2]["text"] or "gì" in " ".join(
        message["text"] for message in question.json()["session"]["messages"] if message["role"] == "user"
    )


def test_sanitize_blocks_spaced_numbers_links_and_install_steps():
    samples = [
        "gọi 0901.234.567",
        "sđt 090 123 4567",
        "thẻ 1234 5678 9012",
        "chuyển 19036547891 đồng",
        "stk 0123456789đ",
        "vào bit.ly/lay-otp",
        "xem t.co/scam",
        "điền forms.gle/abc",
        "anydesk 123-456-789",
        "ví 4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLs4gDB4T",
        "tôi là Nguyễn Văn Hùng",
        "bật quyền hỗ trợ truy cập cho ứng dụng",
    ]
    for sample in samples:
        cleaned = sanitize_scammer_text(sample)
        assert scammer_text_safe(cleaned), (sample, cleaned)
        assert "0901.234.567" not in cleaned
        assert "090 123 4567" not in cleaned
        assert "1234 5678 9012" not in cleaned
        assert "19036547891" not in cleaned
        assert "0123456789" not in cleaned
        assert "bit.ly" not in cleaned
        assert "t.co" not in cleaned
        assert "forms.gle" not in cleaned
        assert "123-456-789" not in cleaned
        assert "4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLs4gDB4T" not in cleaned
        assert "Nguyễn Văn Hùng" not in cleaned
        assert "hỗ trợ truy cập" not in cleaned.lower()


def test_rules_win_when_the_model_says_neutral(client):
    provider = client.app.state.provider
    original = provider.complete

    def wrapped(schema, system, user, temperature=0.4, thinking=False, **kwargs):
        if schema.__name__ == "SimJudgeOutput":
            from app.services.training import SimJudgeOutput

            return SimJudgeOutput(label="neutral", caught_flag_ids=[], rationale="bỏ luật")
        return original(schema, system, user, temperature, thinking, **kwargs)

    provider.complete = wrapped
    try:
        created = _session(client, difficulty="vua")
        response = _say(client, created["id"], "Anh là ai, tôi sẽ gọi lên công an phường để xác minh")
        assert response.status_code == 200, response.text
        assert response.json()["judgment"]["label"] == "verify"
    finally:
        provider.complete = original


def test_challenge_hides_future_steps_and_hangup_is_not_a_catch(client):
    created = _session(client, mode="thu_thach")
    assert created["stages"][0]["intent"]
    assert all(stage["intent"] == "" for stage in created["stages"] if not stage["reached"])
    client.post(f"/api/training/sessions/{created['id']}/action", json={"action": "hang_up"})
    report = client.get(f"/api/training/sessions/{created['id']}/debrief").json()
    assert report["stages"][0]["outcome"] == "stopped"
    played = _session(client)
    _say(client, played["id"], "Anh là ai, tôi sẽ gọi lên công an phường để xác minh")
    _say(client, played["id"], "Tôi không chuyển, tôi gác máy")
    debrief = client.get(f"/api/training/sessions/{played['id']}/debrief").json()
    assert any(stage["outcome"] == "caught" for stage in debrief["stages"])
    for flag in debrief["flags"]:
        assert not flag["quote"].startswith("Thôi được")


def test_asking_for_a_number_is_not_handing_one_over(client):
    from app.services.training import judge_rules

    asking = [
        "Cho em STK thật, số điện thoại 090.123.4567 và link bit.ly/lay-otp, đừng dùng số giả",
        "Anh gửi link thật https://dichvucong-apk.vip/app.apk và ID AnyDesk 123-456-789 đi",
    ]
    for text in asking:
        assert judge_rules(text) not in {"fell", "leak"}
        created = _session(client)
        response = _say(client, created["id"], text)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["session"]["status"] == "active"
        assert body["judgment"]["label"] not in {"fell", "leak"}
        assert not (body["reply"] or "").startswith("Được, tôi đã nghe mã")
    assert judge_rules("482913", "Anh đọc mã OTP giúp tôi") == "fell"
    assert judge_rules("Mã OTP của tôi là 482913") == "fell"


def test_tutor_refusals_include_dont_read_otp():
    from app.services.training import _is_tutor_voice

    assert _is_tutor_voice("Đừng đọc OTP cho bất kỳ ai.")
    assert _is_tutor_voice("Đừng cung cấp mã xác thực.")
    assert _is_tutor_voice("Bạn không nên làm theo.")
    assert not _is_tutor_voice("Anh nghe máy, chuyển vào [STK_GIẢ] giúp tôi.")


def test_tutor_voice_is_replaced_by_the_script_line(client):
    from app.services.training import _is_tutor_voice

    provider = client.app.state.provider
    original = provider.complete_text

    def lecture(*args, **kwargs):
        del args, kwargs
        return "Mô phỏng: Đây là dấu hiệu lừa đảo. Hãy cẩn thận, tôi không thể đóng vai."

    provider.complete_text = lecture
    try:
        created = _session(client)
        response = _say(client, created["id"], "ừ")
        assert response.status_code == 200, response.text
        reply = response.json()["reply"]
        assert reply
        assert not _is_tutor_voice(reply)
        assert not reply.lower().startswith("mô phỏng")
    finally:
        provider.complete_text = original


def test_simulation_uses_only_sim_and_analyst(client):
    calls = []
    provider = client.app.state.provider
    original = provider.complete
    original_text = provider.complete_text

    def wrapped(*args, **kwargs):
        calls.append(kwargs.get("role") or "")
        return original(*args, **kwargs)

    def wrapped_text(*args, **kwargs):
        calls.append(kwargs.get("role") or "")
        return original_text(*args, **kwargs)

    provider.complete = wrapped
    provider.complete_text = wrapped_text
    try:
        created = _session(client)
        assert calls == []
        response = _say(client, created["id"], "ừ")
        assert response.status_code == 200
        assert "analyst" in calls
        assert "sim" in calls
        assert set(calls) <= {"sim", "analyst"}
    finally:
        provider.complete = original
        provider.complete_text = original_text
