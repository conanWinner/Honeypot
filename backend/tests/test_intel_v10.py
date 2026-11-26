"""2025–2026 methods: new IOC kinds, explainable risk, playbooks, IOC graph, warning cards, trends."""

from app.agent.casefile import harvest_indicators, lookalike_reason, valid_crypto_wallet
from app.agent.schemas import PlannerOutput
from app.data.playbooks import playbook_state
from app.data.scripts import SCRIPTS
from app.data.warnings import WARNINGS
from app.llm.base import LLMError
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


def test_disguised_notices_are_scams_and_genuine_ones_stay_low(client):
    scams = [
        "EVN thông báo: quý khách nợ tiền điện kỳ 11, hệ thống sẽ ngắt điện lúc 20h tối nay. Tra cứu và thanh toán ngay tại evn-cskh.top để tránh bị cắt.",
        "Điện lực thông báo: tiền điện kỳ này đã quá hạn, quý khách chuyển khoản 1.250.000đ vào STK 0123456789 để tránh bị cắt điện.",
        "Shopee: đơn hàng đang giao bị giữ tại kho, vui lòng thanh toán phí lưu kho 15.000đ tại shopee-giaohang.top/capnhat.",
        "Vietcombank: mã OTP 482193, không chia sẻ mã này với bất kỳ ai. Em là nhân viên VCB, chị nhắn lại 6 số đó để em xác nhận nhé.",
        "MoMo: ưu đãi hoàn tiền 50%, chuyển 500.000đ kích hoạt vào ví 0987654321 để nhận.",
        "Shipper GHN: chuyển khoản trước 35.000đ phí COD vào STK 19033344455, không chuyển em hoàn đơn.",
    ]
    for text in scams:
        assert not official_notice(text), text
        body = client.post("/api/check", json={"text": text}).json()
        assert body["verdict"] == "scam", (text, body["verdict"], body["risk"])
        assert body["is_scam"] is True
        assert body["risk_score"] > 0
    genuine = [
        "Vietcombank: ma OTP 482193 cua quy khach. Khong chia se ma nay voi bat ky ai.",
        "EVN HANOI thong bao tien dien thang 11. Tra cuu tai evn.com.vn, khong can tai them ung dung.",
        "Shopee: don hang dang giao, shipper se goi truoc khi toi. Khong can chuyen khoan them.",
        "MoMo: uu dai 50% khi thanh toan hoa don dien trong app MoMo chinh thuc.",
    ]
    for text in genuine:
        body = client.post("/api/check", json={"text": text}).json()
        assert body["risk"] == "thap" and body["verdict"] == "benign", (text, body["risk"], body["verdict"])


def test_risk_band_follows_the_score_not_confidence(client):
    body = client.post("/api/check", json={"text": "Shop đổi mã QR mới ở quầy, tên người nhận là kế toán."}).json()
    assert body["risk_score"] < 85
    if body["risk_score"] < 25:
        assert body["risk"] == "thap"
    assert body["risk"] != "rat_cao"


def test_family_biometric_update_is_not_a_scam(client):
    from app.agent.schemas import AnalystOutput
    from app.services.checker import _model_says_benign

    analyst = AnalystOutput(scammer_intent="Tin này không thể hiện hành vi lừa đảo.", scammer_suspicion=0.1)
    assert _model_says_benign(analyst, hot=False) is True
    explicit = AnalystOutput(scammer_intent="có chữ lừa đảo", is_scam=False, scammer_suspicion=0.9)
    assert _model_says_benign(explicit, hot=True) is True

    class SaysNotScam(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            if schema.__name__ == "AnalystOutput":
                base = super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)
                return base.model_copy(update={"scammer_intent": "không thể hiện hành vi lừa đảo", "is_scam": False, "scammer_suspicion": 0.2})
            return super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)

    client.app.state.provider = SaysNotScam()
    try:
        body = client.post(
            "/api/check",
            json={"text": "Con đã cập nhật sinh trắc học trên app ngân hàng rồi mẹ nhé, ra quầy cũng nhanh."},
        ).json()
        assert body["verdict"] != "scam"
        assert body["is_scam"] is False
        assert body["risk"] != "rat_cao"
    finally:
        client.app.state.provider = MockProvider()


def test_wallet_digits_and_otp_are_not_bank_accounts():
    leaked = harvest_indicators("Anh nạp USDT mạng TRC20 vào ví TXk3fakeTronWallet9AbCdEf1234567890 nhé em.")
    assert leaked["bank_accounts"] == []
    otp = harvest_indicators("Vietcombank: ma OTP 482193")
    assert otp["bank_accounts"] == []
    account = harvest_indicators("chuyển vào STK 123456")
    assert "123456" in account["bank_accounts"]


def test_identity_is_not_reasked_when_the_playbook_is_exhausted(client):
    from app.data.playbooks import playbook_for

    bank = playbook_for("bank")
    assert all(row["goal"] != "ask_identity" or row["key"] == "who" for row in bank["targets"])

    class Stuck(MockProvider):
        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            if schema.__name__ == "PlannerOutput":
                return PlannerOutput(goal="ask_identity", rationale="Hỏi lại họ là ai.", tone="ngắn", must_not=[], facts_to_use=[])
            return super().complete(schema, system, user, temperature, thinking=thinking, **kwargs)

    client.app.state.provider = Stuck()
    try:
        created = client.post("/api/conversations", json={"persona_id": "lan-nt"}).json()
        goals = []
        for line in (
            "Bên em là cán bộ văn phòng luật hỗ trợ nạn nhân lấy lại tiền bị lừa.",
            "Phí hồ sơ là 3 triệu.",
            "STK nhận là 1903000111222.",
            "Nhóm luật sư ở t.me/hotro_thuhoi.",
            "Chị còn nghe không.",
        ):
            body = client.post(f"/api/conversations/{created['id']}/messages", json={"text": line})
            assert body.status_code == 200, body.text
            goals.append(body.json()["panel"]["goal"]["goal"])
        assert "ask_identity" not in goals
        assert goals[-1] != "ask_identity"
    finally:
        client.app.state.provider = MockProvider()


def test_dvc_apk_query_prefers_the_apk_script(client):
    items = client.get("/api/scripts", params={"q": "dvc-apk dịch vụ công"}).json()["items"]
    assert items
    assert items[0]["id"] == "dvc-apk-ho-tro-truy-cap"


def test_check_keeps_the_score_when_the_model_times_out(client, monkeypatch):
    def boom(*_args, **_kwargs):
        raise LLMError("timeout")

    monkeypatch.setattr("app.api.routes.check_text", boom)
    body = client.post(
        "/api/check",
        json={"text": "Cán bộ phường: bác cài file DichVuCong.apk rồi đọc mã OTP cho tôi ngay."},
    ).json()
    assert body["risk"] != "thap"
    assert body["risk_score"] >= 25
    assert body["degraded"] is True


def test_trends_and_demos(client):
    trends = client.get("/api/trends").json()
    assert trends["watch"] and trends["stats"]
    assert any(item["id"] in {"telco", "rat", "recovery", "course"} for item in trends["emerging"])
    meta = client.get("/api/demo").json()
    assert len(meta["all"]) >= 2
    started = client.post("/api/demo/start", params={"id": "app-dich-vu-cong-ong-sau"}).json()
    assert started["persona"]["id"] == "ong-sau" and started["demo"]["id"] == "app-dich-vu-cong-ong-sau"
