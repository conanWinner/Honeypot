# Luyện tập — lần chạy mô hình thật

Lần này không có `LLM_API_KEY`, `OPENAI_API_KEY` hay `GEMINI_API_KEY` trong môi trường, nên chưa gọi 9router.

Đường mock (`LLM_PROVIDER=mock`) đã chạy trong `backend/tests/test_training.py`:

- Mở phiên có và không có `script_id`, câu đầu là lời kẻ lừa, trạng thái `active`.
- Đường an toàn (xác minh rồi từ chối) kết thúc `safe`, điểm ≥ 70, tổng kết có bước `caught`.
- Đọc OTP `482913` kết thúc `scammed`, bản lưu chỉ còn `[ĐÃ CHE]`, điểm ≤ 30.
- `share_otp` ra `scammed`, `hang_up` ra `safe`. Phiên đã kết thúc trả 409, id lạ trả 404.
- Hết lượt ra `timeout`, điểm ≤ 70. Một gợi ý trừ đúng 5 điểm.
- `sanitize_scammer_text` xóa số dài, tên chủ tài khoản, đường dẫn, file `.apk`, ID UltraViewer, và giữ nguyên «5 triệu» / «15 phút».
- Mỗi kịch bản đã xuất bản chơi một phiên mock đến hết: không câu nào của kẻ lừa vi phạm bộ lọc an toàn.
- Trắc nghiệm `n=8` có cả hai đáp án, mọi câu hỏi qua bộ lọc an toàn.
- Lượt luyện chỉ gọi vai `sim` và `analyst`.

Khi có khóa router, chạy lại ít nhất ba phiên cho mỗi kiểu kết (`safe`, `scammed`, `timeout`) trên ít nhất năm nhóm, ghi độ trễ từng lượt (trung vị cần dưới 6 giây) và số lần bộ lọc an toàn bắt được. Chỉ dùng `MODEL_SIM=ag/gemini-3.8-flash-low` (dự phòng `cx/gpt-5.6-luna`) và `MODEL_ANALYST=ag/gemini-3.8-flash-low`.
