"""Per-family elicitation playbooks.

For each scam family, the facts that matter most to report it, in the order worth
asking. Each target maps onto an existing planner goal, so the small planner model
does not have to learn new labels. `done_when` names indicator buckets (or checklist
keys) that close the target once the scammer has given them away.
"""

from __future__ import annotations


def _t(key: str, label: str, goal: str, hint: str, done_when: list[str]) -> dict:
    return {"key": key, "label": label, "goal": goal, "hint": hint, "done_when": done_when}


_WHO = _t("who", "Họ xưng là ai, ở đơn vị nào", "ask_identity", "hỏi tên, đơn vị, số hiệu như người cẩn thận", ["checklist:who"])

PLAYBOOKS: dict[str, dict] = {
    "rat": {
        "label": "Cài app chiếm quyền",
        "targets": [
            _WHO,
            _t("apk", "Tên app / file .apk và đường dẫn tải", "ask_link", "hỏi lại tên ứng dụng, xin gửi lại đường dẫn tải vì máy báo lỗi", ["apk", "urls"]),
            _t("zalo", "Zalo/số họ dùng để gửi file", "ask_purpose", "hỏi gửi qua Zalo nào, số nào để lưu cho khỏi nhầm", ["zalo", "phones"]),
            _t("permission", "Họ bắt bật quyền gì", "ask_next_instruction", "hỏi cài xong thì bấm gì, bật cái gì trong cài đặt", ["checklist:app"]),
            _t("remote_id", "ID AnyDesk hoặc UltraViewer", "ask_remote_id", "hỏi họ cần đọc ID nào trên màn hình, chưa cài", ["remote_ids"]),
        ],
    },
    "vneid": {
        "label": "VNeID / giấy tờ",
        "targets": [
            _WHO,
            _t("link", "Trang web hoặc app giả", "ask_link", "nói không tìm thấy, xin gửi lại đường dẫn hoặc tên app", ["urls", "apk"]),
            _t("ask", "Họ đòi thông tin gì (căn cước, OTP, khuôn mặt)", "ask_purpose", "hỏi cần giấy tờ gì, có phải ra phường không", ["checklist:payment"]),
            _t("zalo", "Số hoặc Zalo liên hệ", "ask_purpose", "hỏi số hoặc Zalo để gọi lại", ["zalo", "phones"]),
        ],
    },
    "police": {
        "label": "Giả công an",
        "targets": [
            _WHO,
            _t("account", "Tài khoản 'giám định' nhận tiền", "ask_account_number", "hỏi chuyển vào tài khoản nào, tên ai, ngân hàng nào", ["bank_accounts"]),
            _t("app", "App hoặc phần mềm họ bắt cài", "ask_next_instruction", "hỏi cài ứng dụng gì, tên là gì", ["apps", "apk"]),
            _t("remote", "ID UltraViewer/AnyDesk", "ask_next_instruction", "hỏi họ cần đọc số ID nào", ["remote_ids"]),
            _t("pressure", "Họ dọa gì, cấm gì", "emotional_hook", "hỏi lại nếu không làm thì sao", ["pressure"]),
        ],
    },
    "bank": {
        "label": "Giả ngân hàng",
        "targets": [
            _WHO,
            _t("link", "Đường dẫn / app 'hỗ trợ'", "ask_link", "hỏi cập nhật ở trang nào, xin đường dẫn", ["urls", "apk"]),
            _t("ask", "Họ đòi gì: OTP, khuôn mặt, video", "ask_purpose", "hỏi phải làm những bước gì", ["checklist:payment"]),
            _t("fee", "Phí hoặc bước họ bắt làm trong app", "ask_purpose", "hỏi họ muốn mình bấm gì, có đòi phí hay mã không", ["checklist:payment", "apk"]),
            _t("remote_id", "ID AnyDesk hoặc UltraViewer nếu họ bắt cài", "ask_remote_id", "hỏi ID trên màn hình là số nào, chưa đọc", ["remote_ids"]),
        ],
    },
    "investment": {
        "label": "Đầu tư",
        "targets": [
            _t("platform", "Tên sàn / app giao dịch", "ask_link", "hỏi tên sàn, xin link tải app để xem thử", ["urls", "apk", "apps"]),
            _t("group", "Nhóm Telegram/Zalo", "ask_link", "xin link nhóm để vào xem", ["telegram", "zalo"]),
            _t("wallet", "Ví crypto hoặc tài khoản nạp", "ask_account_number", "hỏi nạp vào đâu, ví nào, mạng gì", ["crypto_wallets", "bank_accounts"]),
            _t("min", "Mức nạp tối thiểu, cách rút", "ask_next_instruction", "hỏi nạp ít nhất bao nhiêu, rút thế nào", ["checklist:payment"]),
        ],
    },
    "romance": {
        "label": "Tình cảm",
        "targets": [
            _t("story", "Họ xưng là ai, ở đâu", "probe_hook", "hỏi chuyện công việc, thành phố họ ở", ["checklist:who"]),
            _t("platform", "Sàn hoặc app họ rủ vào", "ask_link", "hỏi tên sàn, xin link", ["urls", "apk", "apps"]),
            _t("wallet", "Ví USDT hoặc tài khoản nhận", "ask_account_number", "hỏi nạp vào ví nào, mạng gì", ["crypto_wallets", "bank_accounts"]),
        ],
    },
    "job": {
        "label": "Việc làm / nhiệm vụ",
        "targets": [
            _t("group", "Nhóm Telegram/Zalo giao nhiệm vụ", "ask_link", "xin link nhóm để vào nhận việc", ["telegram", "zalo", "urls"]),
            _t("account", "Tài khoản / ví nhận tiền nạp", "ask_account_number", "hỏi nạp vào tài khoản nào", ["bank_accounts", "crypto_wallets"]),
            _t("amount", "Số tiền mỗi nhiệm vụ", "ask_next_instruction", "hỏi nhiệm vụ sau bao nhiêu, rút khi nào", ["checklist:payment"]),
        ],
    },
    "course": {
        "label": "Khóa học / chứng chỉ",
        "targets": [
            _WHO,
            _t("fee", "Phí giữ chỗ hoặc phí thi", "ask_purpose", "hỏi phí gì, bao nhiêu, đóng cho ai", ["checklist:payment"]),
            _t("account", "Tài khoản nhận phí", "ask_account_number", "hỏi chuyển phí vào tài khoản nào", ["bank_accounts"]),
            _t("link", "Link lớp hoặc trang thi", "ask_link", "xin link lớp học hoặc trang thi", ["urls", "telegram", "zalo"]),
        ],
    },
    "recovery": {
        "label": "Lấy lại tiền bị lừa",
        "targets": [
            _WHO,
            _t("fee", "Khoản phí họ đòi", "ask_purpose", "hỏi phí gì, bao nhiêu, có biên lai không", ["checklist:payment"]),
            _t("account", "Tài khoản nhận phí", "ask_account_number", "hỏi chuyển phí vào đâu, tên ai", ["bank_accounts"]),
            _t("group", "Nhóm/Telegram 'luật sư'", "ask_link", "xin link liên hệ luật sư", ["telegram", "zalo", "urls"]),
        ],
    },
    "telco": {
        "label": "Nhà mạng / SIM",
        "targets": [
            _WHO,
            _t("ask", "Họ đòi gì: OTP, căn cước", "ask_purpose", "hỏi chuẩn hóa cần những gì", ["checklist:payment"]),
            _t("link", "Link / app cập nhật", "ask_link", "xin link cập nhật", ["urls", "apk"]),
        ],
    },
    "utility": {
        "label": "Điện nước",
        "targets": [
            _WHO,
            _t("app", "App / link thanh toán", "ask_link", "hỏi tải app ở đâu, xin link", ["urls", "apk"]),
            _t("account", "Tài khoản nhận tiền", "ask_account_number", "hỏi đóng vào tài khoản nào", ["bank_accounts"]),
        ],
    },
    "tax": {
        "label": "Thuế / bảo hiểm",
        "targets": [
            _WHO,
            _t("app", "App VssID/eTax giả, đường dẫn", "ask_link", "hỏi cài bản nào, xin đường dẫn", ["urls", "apk"]),
            _t("account", "Tài khoản nhận phí", "ask_account_number", "hỏi phí nộp vào đâu", ["bank_accounts"]),
        ],
    },
    "travel": {
        "label": "Du lịch / đặt phòng",
        "targets": [
            _t("page", "Fanpage / web đặt phòng", "ask_link", "xin link trang để xem ảnh phòng", ["urls"]),
            _t("account", "Tài khoản nhận cọc", "ask_account_number", "hỏi cọc vào tài khoản nào, tên ai", ["bank_accounts"]),
            _t("hotline", "Số liên hệ", "ask_identity", "hỏi số hotline", ["phones"]),
        ],
    },
}

DEFAULT = {
    "label": "Chung",
    "targets": [
        _WHO,
        _t("payment", "Họ muốn mình làm gì", "ask_purpose", "hỏi lại cần làm gì, đóng khoản gì, để làm gì", ["checklist:payment"]),
        _t("account", "Tài khoản hoặc ví nhận tiền", "ask_account_number", "hỏi chuyển vào đâu, tên chủ tài khoản là ai", ["bank_accounts", "crypto_wallets"]),
        _t("link", "Đường dẫn hoặc file", "ask_link", "xin gửi lại đường dẫn vì bấm không vào", ["urls", "apk"]),
        _t("app", "Ứng dụng họ bắt dùng", "ask_next_instruction", "hỏi phải cài hay mở ứng dụng nào", ["apps", "remote_ids", "checklist:app"]),
        _t("pressure", "Cách gây sức ép", "emotional_hook", "hỏi nếu chậm thì sao, hạn đến bao giờ", ["checklist:pressure"]),
    ],
}

ALIASES = {
    "momo": "bank",
    "shipper": "utility",
    "ecommerce": "bank",
    "relative": "police",
    "deepfake": "police",
    "hijack": "job",
    "prize": "tax",
    "loan": "recovery",
    "rental": "travel",
    "charity": "recovery",
    "qr": "travel",
}


def playbook_for(category: str) -> dict:
    return PLAYBOOKS.get(category) or PLAYBOOKS.get(ALIASES.get(category, ""), DEFAULT)


def playbook_state(category: str, checklist: list[dict], indicators: dict) -> dict:
    book = playbook_for(category or "")
    done_keys = {item.get("key") for item in checklist or [] if item.get("done")}
    rows = []
    for target in book["targets"]:
        hit = ""
        for cond in target["done_when"]:
            if cond.startswith("checklist:"):
                if cond.split(":", 1)[1] in done_keys:
                    hit = "✓"
                    break
            elif (indicators or {}).get(cond):
                hit = str((indicators or {}).get(cond)[-1])
                break
        rows.append(
            {
                "key": target["key"],
                "label": target["label"],
                "goal": target["goal"],
                "hint": target["hint"],
                "done": bool(hit),
                "detail": "" if hit == "✓" else hit,
            }
        )
    nxt = next((row for row in rows if not row["done"]), None)
    return {"category": category or "", "label": book["label"], "targets": rows, "next": nxt}


def next_unasked(book: dict, asked_keys: list[str]) -> dict | None:
    """Skip targets already answered or already asked, so identity is not repeated."""
    asked = set(asked_keys or [])
    for row in book.get("targets") or []:
        if row.get("done") or row.get("key") in asked:
            continue
        return row
    return None
