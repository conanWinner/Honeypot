"""2025–2026 methods: new IOC kinds, explainable risk, playbooks, IOC graph, warning cards, trends."""

from app.agent.casefile import harvest_indicators, lookalike_reason, valid_crypto_wallet
from app.agent.schemas import PlannerOutput
from app.data.playbooks import playbook_state
from app.data.scripts import SCRIPTS
from app.data.warnings import WARNINGS
from app.llm.mock import MockProvider
from app.services.risk import merge_factors, official_notice, score_text
from app.taxonomy import CATEGORIES

_WALLET = "T9AbCdEfGhJkMnPqRsTuVwXyZ23456789a"


def test_new_ioc_kinds():
    found = harvest_indicators(
        "Tải file DichVuCong.apk ở dichvucong-gov.top/app, bật quyền Hỗ trợ truy cập. "
        "Vào nhóm t.me/nhiemvu_vip88 hoặc zalo.me/g/mau-nhi. "
        f"Nạp USDT TRC20 vào ví {_WALLET}. "
        "Đọc ID UltraViewer 123 456 789."
    )
    assert found["apk"] == ["dichvucong.apk"]
    assert "dichvucong-gov.top/app" in found["urls"]
    assert found["telegram"] == ["t.me/nhiemvu_vip88"]
    assert found["zalo"] == ["zalo.me/g/mau-nhi"]
    assert found["crypto_wallets"] == [_WALLET]
    assert found["remote_ids"] == ["123456789"]
    assert "123456789" not in found["phones"] and "123456789" not in found["bank_accounts"]
    assert any("Hỗ trợ truy cập" in item for item in found["techniques"])
    assert found["lookalikes"]
    assert not harvest_indicators("ví 0x52908400098527886E0F7030069857D2E4169EE7 ERC20")["bank_accounts"]


def test_crypto_wallets_reject_made_up_strings():
    assert valid_crypto_wallet(_WALLET)
    assert valid_crypto_wallet("0x52908400098527886E0F7030069857D2E4169EE7")
    assert valid_crypto_wallet("bc1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq")
    assert valid_crypto_wallet("1BoatSLRHtKNngkdXEeobR76b53LETtpyT")
    assert not valid_crypto_wallet("TXk3fakeTronWallet9AbCdEf1234567890")
    assert not valid_crypto_wallet("TQx9notavalid")
    assert not valid_crypto_wallet("0xzzzz")
    assert not valid_crypto_wallet("bc1short")
    assert not valid_crypto_wallet("not-a-wallet")
    rejected = harvest_indicators("nạp vào ví TXk3fakeTronWallet9AbCdEf1234567890 và 0xzzzz và bc1notlong")
    assert rejected["crypto_wallets"] == []


def test_lookalike_domains():
    assert lookalike_reason("vcb-sinhtrachoc.top")
    assert lookalike_reason("https://evn-cskh.top/a.apk")
    assert not lookalike_reason("https://www.vietcombank.com.vn/abc")
    assert not lookalike_reason("dichvucong.gov.vn")
    assert not lookalike_reason("google.com")


def test_risk_score_explains_and_stays_low_on_household():
    scam = score_text("Cán bộ công an phường: bác cài file DichVuCong.apk rồi đọc mã OTP cho tôi ngay trong hôm nay.")
    codes = {item["code"] for item in scam["factors"]}
    assert {"install", "otp", "authority"} <= codes
    assert scam["score"] >= 50 and scam["level"] in {"cao", "rat_cao"}
    assert all(item["label"] for item in scam["factors"])
    plain = score_text("Tối nay em chuyển tiền điện tháng này cho anh nhé.")
    assert plain["score"] <= 20 and plain["level"] == "thap"
    live = merge_factors(scam["factors"][:1], scam["factors"])
    assert live["score"] == scam["score"]
    weak = score_text("Anh ơi có một đường dẫn lạ.")
    assert weak["level"] != "rat_cao"


def test_official_notices_stay_low(client):
    samples = [
        "Vietcombank: ma OTP 482193 cua quy khach. Khong chia se ma nay voi bat ky ai.",
        "EVN HANOI thong bao tien dien thang 11. Tra cuu tai evn.com.vn, khong can tai them ung dung.",
        "Shopee: don hang dang giao, shipper se goi truoc khi toi. Khong can chuyen khoan them.",
        "MoMo: uu dai 50% khi thanh toan hoa don dien trong app MoMo chinh thuc.",
    ]
    for text in samples:
        assert official_notice(text), text
        body = client.post("/api/check", json={"text": text}).json()
        assert body["risk"] == "thap", (text, body["risk"], body["verdict"])
        assert body["is_scam"] is False
        assert body["verdict"] == "benign"
        assert body["risk_score"] == 0


def test_playbook_tracks_family_targets():
    book = playbook_state("rat", [{"key": "who", "done": True}], {"apk": ["x.apk"]})
    keys = {row["key"]: row["done"] for row in book["targets"]}
    assert keys["who"] and keys["apk"] and not keys["remote"]
    assert book["next"] and book["next"]["goal"] in {"ask_purpose", "ask_next_instruction", "ask_link"}
    assert playbook_state("momo", [], {})["targets"]
    recovery = playbook_state("recovery", [], {})
    assert [row["key"] for row in recovery["targets"][:4]] == ["who", "fee", "account", "group"]


def test_recovery_playbook_moves_past_identity(client):
    class Stuck(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            if schema.__name__ == "PlannerOutput":
                return PlannerOutput(goal="ask_identity", rationale="Hỏi lại họ là ai.", tone="ngắn", must_not=[], facts_to_use=[])
            return super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)

    client.app.state.provider = Stuck()
    try:
        created = client.post("/api/conversations", json={"persona_id": "lan-nt"}).json()
        lines = [
            "Bên em là cán bộ văn phòng luật hỗ trợ nạn nhân lấy lại tiền bị lừa, phối hợp với công an.",
            "Chị nghe rõ chưa ạ.",
            "Chị còn đó không.",
        ]
        goals = []
        replies = []
        for line in lines:
            body = client.post(f"/api/conversations/{created['id']}/messages", json={"text": line})
            assert body.status_code == 200, body.text
            panel = body.json()["panel"]
            goals.append(panel["goal"]["goal"])
            replies.append(body.json()["victim_message"]["content"].lower())
        assert all("là ai" not in reply for reply in replies)
        assert goals == ["ask_purpose", "ask_account_number", "ask_link"]
    finally:
        client.app.state.provider = MockProvider()


def test_seed_data_is_consistent():
    ids = [row["id"] for row in SCRIPTS]
    assert len(ids) == len(set(ids))
    assert all(row["category"] in CATEGORIES for row in SCRIPTS)
    course = next(row for row in SCRIPTS if row["id"] == "khoa-hoc-thi-chung-chi")
    assert "chứng chỉ" in course["title"]
    assert course["category"] == "course"
    for card in WARNINGS:
        assert card["sources"] and all(src["url"].startswith("https://") for src in card["sources"])
        assert all(cat in CATEGORIES for cat in card["categories"])


def test_warning_and_intel_endpoints(client):
    cards = client.get("/api/warnings").json()
    assert len(cards["cards"]) >= 12 and cards["stats"]
    assert cards["cards"][0]["rising"] is True
    detail = client.get("/api/warnings/app-dich-vu-cong-gia").json()
    assert any(row["id"] == "dvc-apk-ho-tro-truy-cap" for row in detail["scripts"])
    assert client.get("/api/warnings/khong-co").status_code == 404
    graph = client.get("/api/intel/graph").json()
    assert graph["stats"]["iocs"] > 0
    hits = client.get("/api/intel/lookup", params={"q": "0123456789012"}).json()["hits"]
    assert any(hit["count"] >= 1 for hit in hits)


def test_chat_panel_has_risk_timeline_playbook(client):
    created = client.post("/api/conversations", json={"persona_id": "ong-sau", "channel": "web"}).json()
    lines = [
        "Cháu là cán bộ công an phường, hồ sơ cư trú của chú bị sai, phải cập nhật trong hôm nay.",
        "Cháu gửi file DichVuCong.apk ở dichvucong-gov.top/app, chú bấm tải rồi cài đặt.",
        "Chuyển phí vào số tài khoản 0123456789012 Vietcombank nhé chú.",
    ]
    panel = None
    for line in lines:
        response = client.post(f"/api/conversations/{created['id']}/messages", json={"text": line})
        assert response.status_code == 200, response.text
        panel = response.json()["panel"]
    assert panel["risk"]["score"] >= 50 and panel["risk"]["factors"]
    assert len(panel["timeline"]) == 3
    assert any("APK" in item for entry in panel["timeline"] for item in entry["new_iocs"])
    assert panel["playbook"]["targets"]
    assert any(link["value"] == "0123456789012" for link in panel["ioc_links"])
    graph = client.get("/api/intel/graph").json()
    assert graph["stats"]["shared_iocs"] >= 1


def test_check_returns_explanation(client):
    body = client.post(
        "/api/check",
        json={"text": "Điện lực báo nợ tiền điện, anh tải ứng dụng qua https://evn-cskh.top/EVN.apk và bật quyền hỗ trợ truy cập."},
    ).json()
    assert body["verdict"] == "scam"
    assert body["risk_score"] >= 50
    assert any(item["code"] == "install" for item in body["risk_factors"])
    assert body["indicators"].get("apk")
    benign = client.post("/api/check", json={"text": "Mẹ ơi tối nay con về muộn, mẹ ăn cơm trước nhé."}).json()
    assert benign["risk_score"] == 0 and benign["risk_factors"] == []


def test_trends_and_demos(client):
    trends = client.get("/api/trends").json()
    assert trends["watch"] and trends["stats"]
    assert any(item["id"] in {"telco", "rat", "recovery", "course"} for item in trends["emerging"])
    meta = client.get("/api/demo").json()
    assert len(meta["all"]) >= 2
    started = client.post("/api/demo/start", params={"id": "app-dich-vu-cong-ong-sau"}).json()
    assert started["persona"]["id"] == "ong-sau" and started["demo"]["id"] == "app-dich-vu-cong-ong-sau"
