"""Shared labels. Codes stay stable in the database; the UI speaks Vietnamese."""

CATEGORIES: dict[str, str] = {
    "police": "Giả danh công an",
    "bank": "Giả danh ngân hàng",
    "momo": "Giả danh ví điện tử",
    "shipper": "Shipper / giao hàng",
    "relative": "Giả danh người thân",
    "hijack": "Chiếm tài khoản bạn bè",
    "prize": "Trúng thưởng",
    "investment": "Đầu tư",
    "romance": "Tình cảm",
    "job": "Việc làm / nhiệm vụ",
    "loan": "Vay tiền",
    "utility": "Điện nước",
    "vneid": "VNeID / giấy tờ",
    "tax": "Thuế / bảo hiểm",
    "ecommerce": "Sàn thương mại",
    "deepfake": "Deepfake / cuộc gọi giả",
    "charity": "Từ thiện",
    "rental": "Nhà ở / cọc",
    "rat": "Cài app chiếm quyền",
    "recovery": "Lấy lại tiền bị lừa",
    "telco": "Nhà mạng / SIM",
    "travel": "Du lịch / đặt phòng",
    "qr": "Mã QR giả",
    "course": "Khóa học / chứng chỉ",
    "other": "Khác",
}

CHANNELS: dict[str, str] = {
    "phone": "Điện thoại",
    "zalo": "Zalo",
    "sms": "SMS",
    "facebook": "Facebook",
    "web": "Web",
    "telegram": "Telegram",
    "multi": "Nhiều kênh",
}

GOALS: dict[str, str] = {
    "ask_identity": "Hỏi họ là ai",
    "ask_purpose": "Hỏi mục đích",
    "feign_confusion": "Giả vờ chưa hiểu",
    "stall": "Kéo dài, chưa làm gì",
    "ask_link": "Xin đường dẫn",
    "ask_transfer_destination": "Hỏi chuyển đi đâu",
    "ask_account_number": "Hỏi số tài khoản của họ",
    "read_fake_otp": "Đọc OTP giả",
    "ask_next_instruction": "Hỏi bước tiếp theo",
    "emotional_hook": "Lộ vẻ lo, bắt nói rõ",
    "probe_hook": "Đào đúng chi tiết vừa bịa",
    "close_polite": "Khép khi kịch bản đã đủ",
}

GOAL_NAMES = list(GOALS)
