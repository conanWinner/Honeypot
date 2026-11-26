"""Genuine messages for the quick quiz. No phone numbers, links, or account numbers."""

SAFE_MESSAGES: list[dict] = [
    {
        "text": "Mã OTP của bạn là [MÃ]. Không chia sẻ mã này cho bất kỳ ai, kể cả người tự xưng nhân viên ngân hàng.",
        "channel": "sms",
        "explain": "Tin thật từ ngân hàng nhắc bạn giữ mã, và không hỏi bạn đọc mã cho ai.",
    },
    {
        "text": "Số dư tài khoản của quý khách vừa thay đổi. Mở ứng dụng ngân hàng bạn tự cài để xem chi tiết.",
        "channel": "sms",
        "explain": "Báo thay đổi số dư và bảo mở app chính thức, không gửi đường dẫn.",
    },
    {
        "text": "Em tới cổng rồi, chị xuống nhận hàng giúp em.",
        "channel": "phone",
        "explain": "Shipper báo đã tới nơi, không đòi phí qua đường dẫn lạ.",
    },
    {
        "text": "Nhắc lịch khám ngày mai lúc 9 giờ. Bạn đến quầy lễ tân và không cần chuyển khoản trước.",
        "channel": "sms",
        "explain": "Nhắc lịch hẹn, không đòi tiền và không đòi mã.",
    },
    {
        "text": "Cuộc họp nhóm lúc 14 giờ ngày mai tại phòng họp. Nhớ mang tài liệu đã in.",
        "channel": "zalo",
        "explain": "Nhắc việc nội bộ, không có yêu cầu chuyển tiền hay cài ứng dụng.",
    },
    {
        "text": "Gói cước của bạn sẽ gia hạn trong ứng dụng nhà mạng bạn đang dùng. Không cần bấm tin nhắn lạ.",
        "channel": "sms",
        "explain": "Nhà mạng nhắc gia hạn trong ứng dụng sẵn có, không gửi file cài đặt.",
    },
    {
        "text": "Cảm ơn bạn đã thanh toán tại quầy. Biên lai nằm trong ứng dụng ngân hàng.",
        "channel": "sms",
        "explain": "Xác nhận một giao dịch đã xong, không xin thêm mã.",
    },
    {
        "text": "Con về đến nhà rồi mẹ ơi.",
        "channel": "zalo",
        "explain": "Tin nhắn thường giữa người thân, không đòi chuyển khoản.",
    },
    {
        "text": "Lịch học bù vào thứ bảy, 8 giờ sáng, tại lớp. Không đóng thêm khoản nào.",
        "channel": "zalo",
        "explain": "Nhà trường nhắc lịch, và nói rõ không thu thêm.",
    },
    {
        "text": "Đơn hàng đã giao cho bưu tá. Bạn theo dõi trong ứng dụng của sàn, không chuyển khoản cho số lạ.",
        "channel": "sms",
        "explain": "Báo trạng thái đơn và dặn không chuyển khoản cho người lạ.",
    },
]
