# Kế hoạch: agent xử lý kịch bản hoàn toàn mới

Ngày lập: 26/11/2026. Hạn sơ khảo: 03/12/2026.

## Vì sao cần làm

Honeypot tồn tại để thu chiêu lừa **mới**. Đọc lại mã thì đường đi của một chiêu mới đang có bốn lỗ hổng:

| # | Vấn đề | Chỗ trong mã |
|---|---|---|
| 1 | "Nhánh mới" chỉ bật khi kẻ lừa nhắc hoàn cảnh riêng của persona (`hook_tokens`). Hệ thống không nhận ra một **loại** lừa chưa từng thấy. | `services/matching.py` `branch_hint` |
| 2 | Không có trạng thái "chưa khớp". `search_scripts` luôn trả top 6, không có ngưỡng tối thiểu. Planner bám kịch bản sai và hỏi theo playbook của nhóm sai. | `services/matching.py` `search_scripts`, `agent/orchestrator.py` `_playbook_brief` |
| 3 | Lúc trích xuất, `duplicate` gọi `_merge_into` và **ghi thẳng vào kịch bản đã xuất bản**, không qua kiểm duyệt. Một chiêu mới khớp nhầm với độ tin cậy ≥ 0.62 bị nuốt vào kịch bản cũ. | `services/library.py` `finish_conversation` |
| 4 | Eval không có chiêu mới nào. Cả chín tình huống đều có `expected_script` đã nằm trong thư viện. | `eval/scenarios.py` |

## Số đo hiện tại (mock, chỉ từ khóa)

Đo bằng `search_scripts` trên 48 kịch bản gốc:

| Loại | Điểm theo lượt | Điểm cả bản thoại | Kịch bản top qua các lượt |
|---|---|---|---|
| 8 chiêu đã có | 0.74 – 0.97 | 0.86 – 0.97 | Giữ một kịch bản |
| Phạt nguội CSGT (mới) | 0.31 – 0.65 | 0.51 | Đổi liên tục: học phí → bưu điện → khóa học |
| Bác sĩ bán thuốc (mới) | 0.31 – 0.64 | 0.63 | Đổi liên tục: chứng khoán → BHXH → vé máy bay |
| Hãng bay hủy chuyến, hoàn vé | 0.41 – 0.81 | 0.92 | Shopee hoàn tiền (cùng cơ chế, khác thương hiệu) |

Kết luận: chỉ điểm số thì chưa đủ để tách chiêu mới. Tín hiệu rõ hơn là **độ ổn định**: chiêu đã biết giữ nguyên một họ kịch bản qua các lượt, chiêu mới nhảy họ liên tục. Lưu ý: `match_history` đã bị làm "dính" (`_stick` và `stabilize_family`), nên phải ghi riêng kết quả tìm kiếm thô của từng lượt.

## Nguyên tắc thiết kế

1. **Agent không cần biết trước kịch bản.** Khi chưa khớp chắc, agent chạy theo playbook "Chung": moi danh tính, yêu cầu, số tài khoản hoặc ví, đường dẫn, ứng dụng, cách gây sức ép. Các mục này giống nhau ở mọi chiêu.
2. **Thư viện chỉ là gợi ý trong lúc chat.** Chỉ đưa kịch bản khớp cho Planner khi khớp chắc.
3. **Phân loại một lần, trên cả bản thoại, lúc trích xuất.**
4. **Không gì vào thư viện công khai mà không qua người duyệt.** Gộp trùng cũng phải qua hàng chờ.

## Thay đổi

### A. Trạng thái "chưa khớp" trong từng lượt

- `AgentState` thêm `retrieval_log`: mỗi lượt ghi `{family, script_id, score}` của kết quả tìm kiếm **thô**, chưa qua dính.
- Hàm mới `match_strength(log, ...)` ở `services/matching.py` trả về `weak`, `family`, `score` và `consistency` (tỷ lệ các lượt gần đây có cùng họ).
- Yếu khi: điểm thô lượt này < `MATCH_WEAK_SCORE` (0.55), **hoặc** từ lượt thứ 3 trở đi mà tỷ lệ cùng họ trong ba lượt gần nhất < 0.5.
- Khi yếu: Planner nhận `top_match = null`, playbook là "Chung", `playbook_category` để trống. Panel có cờ `unmatched` để Phòng phân tích hiện "Chưa khớp kịch bản nào".
- Analyst vẫn chạy và vẫn hiện danh sách gần giống cho người phân tích. Chỉ phần điều khiển cuộc thoại bỏ qua.

### B. Playbook "Chung" đủ dùng cho chiêu lạ

`DEFAULT` trong `data/playbooks.py` mở rộng thành 6 mục: họ là ai, họ muốn mình làm gì, tài khoản hoặc ví, đường dẫn hoặc file, ứng dụng, cách gây sức ép. Mỗi mục gắn vào một goal Planner đã có, nên không phải đổi prompt.

### C. Phân loại lúc trích xuất

Trong `finish_conversation`:

1. Tìm thư viện bằng **toàn bộ lời kẻ lừa** (một lần embed) để lấy họ gần nhất và điểm.
2. Tính độ ổn định từ `retrieval_log`: tỷ lệ lượt có cùng họ với kết quả bước 1.
3. Quyết định:

| Điều kiện | Quan hệ |
|---|---|
| Điểm cả bản thoại < `EXTRACT_STRONG_SCORE` (0.80) **hoặc** độ ổn định < `EXTRACT_MIN_CONSISTENCY` (0.5) | `new_root`, ghi chú "gần nhất: X" |
| Khớp chắc và có sự kiện nhánh mới | `variant` của họ đó |
| Khớp chắc, không có nhánh mới | `duplicate`, **đề xuất gộp** |

Các ngưỡng là hằng số đầu `backend/app/services/matching.py`, vì điểm khi có embedding thật khác với mock. Cần đo lại khi có khóa.

### D. Gộp trùng phải qua kiểm duyệt

- Bảng `scripts` thêm `relation` và `merge_target`, thêm bằng `_ensure_column` cho DB đang chạy.
- `duplicate` không còn gọi `_merge_into`. Hệ thống tạo bản `pending` với `merge_target` là kịch bản đích, `parent_id` để trống.
- `POST /moderation/{id}/approve` nhận `mode`:
  - `merge` (mặc định khi có `merge_target`): gộp câu chữ và chỉ dấu vào kịch bản đích, bản chờ chuyển sang `merged`.
  - `publish`: người duyệt không đồng ý là trùng, công bố thành kịch bản riêng.
- Giao diện kiểm duyệt hiện nhãn quan hệ (Mới / Nhánh / Đề xuất gộp vào …) và hai nút tương ứng. Thông báo sau khi trích trong ChatRoom nói đúng hành động.

### E. Eval cho chiêu mới

- Thêm ba tình huống không có trong 48 kịch bản gốc: phạt nguội CSGT, bác sĩ bán thuốc, hãng bay hủy chuyến.
- Mỗi tình huống có `expected_relation` và `expected_indicators`.
- `eval/run.py` chạy thêm bước trích xuất và chấm ba chỉ số mới:
  - quan hệ đúng (chiêu mới phải là `new_root`, hoặc `variant` cho hãng bay),
  - số lượt chạy ở chế độ "chưa khớp",
  - chỉ dấu moi được (số tài khoản, đường dẫn).
- Chạy lại và commit báo cáo mock mới.

### F. Kiểm thử

- Chiêu mới → `new_root`, không gắn `parent_id`.
- Chiêu đã biết → bản chờ `duplicate`. Kịch bản gốc **không đổi** cho tới khi duyệt.
- Duyệt `merge` thì kịch bản gốc tăng `occurrence_count` và bản chờ thành `merged`. Duyệt `publish` thì thành kịch bản riêng.
- Lượt đầu của chiêu mới: Planner không nhận `top_match`, playbook là "Chung".
- Toàn bộ test cũ vẫn qua.

### G. Tài liệu

README (pipeline, hàng chờ, số eval mới) và `docs/kien-truc-chi-tiet.md` (ngưỡng, độ ổn định).

## Ngoài phạm vi lần này

- Viết lại orchestrator, bỏ cơ chế dính họ.
- Chuyển luồng "giao cho agent" từ trang Báo cáo sang Phòng phân tích. Việc này để làm riêng sau.
- Đo lại ngưỡng trên mô hình thật. Cần khóa API.

## Rủi ro

- Ngưỡng được chỉnh trên mock, với câu trong eval chép gần nguyên văn từ kịch bản gốc. Trên embedding thật, điểm sẽ khác và phải đo lại.
- Chế độ "chưa khớp" có thể bật nhầm ở lượt đầu của chiêu đã biết khi câu mở quá chung chung. Hệ quả nhẹ: agent hỏi theo playbook chung một lượt.
