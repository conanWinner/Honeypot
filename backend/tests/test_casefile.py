from app.agent.casefile import cue_branch, harvest_indicators, next_gap, update_casefile
from app.agent.state import AgentState


def test_indicators_pull_accounts_urls_and_apps():
    found = harvest_indicators(
        "Chuyển vào 0123456789012 Vietcombank, cài UltraViewer, bấm https://vi-momo.example/khoa trong 15 phút. Gọi 0912000111."
    )
    assert "0123456789012" in found["bank_accounts"]
    assert found["urls"]
    assert "ultraviewer" in found["apps"]
    assert "Vietcombank" in found["brands"]
    assert found["pressure"]
    assert "0912000111" in found["phones"]
    assert "04123456789" not in found["phones"]
    assert "0123456789012" not in found["phones"]
    bank = harvest_indicators("MB Bank 0399888777, stk này nhận phí.")
    assert "0399888777" in bank["bank_accounts"]
    assert "0399888777" not in bank["phones"]
    bare = harvest_indicators("Vào xac-minh.vn rồi làm theo.")
    assert any("xac-minh.vn" in item for item in bare["urls"])


def test_checklist_marks_who_and_payment():
    state = AgentState(persona_slug="ba-nam", fake_otp="111111")
    update_casefile(state, "Tôi là thiếu tá cơ quan cảnh sát điều tra. Bác chuyển tiền trong 15 phút.")
    done = {item["key"] for item in state.checklist if item["done"]}
    assert "who" in done
    assert "payment" in done
    assert "pressure" in done
    assert next_gap(state) == "channel"


def test_cue_branch_spots_a_new_circumstance():
    cue = cue_branch("Tôi biết bà vừa trúng vé số độc đắc hôm qua.", "kịch bản công an tài khoản giám định")
    assert cue is not None
    assert cue["kind"] == "new"
    assert cue_branch("Tôi thấy con trai đang du học ở Đức.", "con trai đang du học ở Đức") is None
