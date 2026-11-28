# Kịch bản demo cho buổi chấm

Mục tiêu: trong khoảng 8 phút, cho giám khảo thấy hết một vòng. Chiêu lừa chưa ai biết, agent tự moi ra cách làm và nơi nhận tiền, hệ thống ghi nhận rồi báo cho người dùng, và có hồ sơ gửi được cho ngân hàng hoặc MoMo.

Mọi số tài khoản, ví và đường dẫn trong demo đều bịa ra. Danh sách kịch bản nằm ở [backend/app/services/demo.py](../backend/app/services/demo.py).

## Trước khi lên sân khấu

1. Chọn cách chạy:
   - **Mô hình thật** (`docker compose up -d --build`): giọng nạn nhân tự nhiên, mỗi lượt khoảng 12 giây.
   - **Mock** (`LLM_PROVIDER=mock docker compose up -d --build`): không cần mạng hay khóa, mỗi lượt dưới 1 giây. Câu trả lời lấy từ mẫu soạn sẵn, nhưng pipeline vẫn là pipeline thật: phân loại, xác nhận số, hồ sơ, vòng chiêu mới. Nên mở sẵn một bản mock để dự phòng khi mạng ở hội trường chập chờn.
2. Vào `/phan-tich/kiem-duyet`, nhập `ADMIN_TOKEN` một lần. Nút «Duyệt ngay» trong chat và nút «Đặt lại dữ liệu demo» dùng lại mã này.
3. Ở `/phan-tich/demo`, bấm **Đặt lại dữ liệu demo**, để các chiêu mới vẫn còn là "mới".
4. Mở sẵn ba tab: `/phan-tich/demo`, `/` (Trang chủ), `/phan-tich/noi-nhan-tien`.

## Lời dẫn và thao tác

| Phút | Màn hình | Thao tác | Câu nói |
| --- | --- | --- | --- |
| 0:00 | Demo | Chọn **Chiêu mới: giả CSGT báo phạt nguội** | "Chiêu này không có trong 48 kịch bản của hệ thống. Tôi sẽ đóng vai kẻ lừa." |
| 0:20 | Chat | Bấm «Tự đi nốt các câu gợi ý» | "Buồng lái báo chưa khớp kịch bản nào. Agent không đoán bừa mà hỏi theo bộ câu hỏi chung: ai gọi, muốn gì, chuyển vào đâu." |
| 1:30 | Chat | Chỉ vào câu ông Sáu đọc lại số tài khoản | "Ông Sáu đọc lại số như người đang chép ra giấy. Kẻ lừa xác nhận, kèm tên chủ tài khoản." |
| 2:00 | Chat | Chỉ vào câu "không rành chuyển khoản, có cách nào khác không" | "Viện một trở ngại vô hại, thế là kẻ lừa đưa thêm ví MoMo." |
| 2:30 | Chat | Bấm **Trích xuất** | "Hệ thống so cả bản thoại với thư viện, không khớp chắc, nên tạo kịch bản gốc mới và đưa vào hàng chờ. Chưa có gì hiện cho người dùng." |
| 3:00 | Chat | Bấm **Duyệt ngay** | "Người duyệt đồng ý." |
| 3:15 | Trang chủ | Tải lại | "Người dùng thấy ngay mục Chiêu mới ghi nhận. Ô kiểm tra tin nhắn cũng đã nhận ra chiêu này." Dán thử một tin phạt nguội vào ô kiểm tra. |
| 4:00 | Chat | Bấm **Xuất hồ sơ** → **In / Lưu PDF** | "Đây là hồ sơ tố giác: nơi nhận tiền nào đã được xác nhận, đường dẫn, dòng thời gian, mã băm chống sửa. Gửi được cho ngân hàng, MoMo hay công an." |
| 5:00 | Demo | Chạy **Chiêu mới: đổi bằng lái sang mẫu mới** | "Chiêu khác, nạn nhân khác. Nhưng xem tài khoản nhận tiền…" |
| 6:30 | Nơi nhận tiền | Mở tab | "Cùng một tài khoản đứng sau hai chiêu khác nhau, nên đây là một đường dây. Đây là danh sách MoMo và ngân hàng có thể dùng để khóa ví, tải CSV được." |
| 7:15 | Demo | Chạy lại **phạt nguội** (tuỳ chọn) | "Lần này hệ thống nhận ra chiêu đã biết, chỉ đề xuất gộp, không tạo bản trùng." |

## Các kịch bản có sẵn

| Loại | Kịch bản | Persona | Điểm nhấn |
| --- | --- | --- | --- |
| Mới | Giả CSGT báo phạt nguội | Ông Sáu, 72 | Tài khoản, rồi ví MoMo dự phòng. Tài khoản dùng chung với chiêu bằng lái |
| Mới | Đổi bằng lái sang mẫu mới qua mạng | Khoa, tài xế công nghệ | Dùng chung tài khoản với chiêu phạt nguội |
| Mới | Giả trợ lý bác sĩ bán thuốc đặc trị | Bà Năm, 68 | Người già có bệnh nền, thu cọc |
| Mới | Giả trung tâm tiêm chủng giảm giá vắc-xin | Chị Thư, mẹ bỉm | Ví MoMo nhận cọc, đúng thứ MoMo khóa được |
| Mới | Nhờ bình chọn cuộc thi, chiếm Facebook | Minh, sinh viên | Không đòi tiền; agent không tự nhắc chuyện tiền |
| Đã biết | Công an gọi, tài khoản giám định | Bà Năm | Nhánh con ở Đức (đã có) và sống một mình (mới) |
| Đã biết | Cán bộ phường bắt cài app Dịch vụ công | Ông Sáu | File APK, quyền Hỗ trợ truy cập |
| Đã biết | Hẹn hò rồi rủ nạp USDT | Tuấn | Ví TRC20 |
| Đã biết | Văn phòng luật hứa lấy lại tiền | Chị Lan | Lừa lần hai, nhóm Telegram |

Điểm embedding thật của cả bản thoại so với thư viện, đo ngày 27/11/2026 với ngưỡng 0,80:
- Chiêu đã biết: 0,90–0,97.
- Chiêu mới: 0,58–0,69.

Test `backend/tests/test_demo_dossier.py` chạy cả chín kịch bản trên mock và kiểm tra quan hệ mà mỗi kịch bản hứa.

## Nếu có sự cố

- **Router chậm hoặc lỗi:** mỗi vai đổi sang model dự phòng, rồi sang `MODEL_LAST_RESORT`. Nếu vẫn lỗi, persona nói câu giữ chỗ trong vai, cuộc chat không treo.
- **Duyệt báo "Cần mã quản trị":** nhập `ADMIN_TOKEN` ở tab Kiểm duyệt rồi bấm lại.
- **Chiêu mới bị nhận là đã biết:** quên đặt lại dữ liệu demo. Bấm «Đặt lại dữ liệu demo» rồi chạy lại.
