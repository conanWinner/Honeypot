# Kiến trúc chi tiết

Tài liệu này bổ sung cho sơ đồ trong README. Mã nguồn là `backend/app/agent/orchestrator.py`, `backend/app/agent/policy.py`, `backend/app/agent/casefile.py`, `backend/app/services/library.py`, `backend/app/services/matching.py`, `backend/app/services/training.py` và `backend/app/llm/factory.py`.

Vòng một lượt là các hàm trên state, hợp đồng đầu ra là model Pydantic. Adapter kênh đứng ngoài vòng và gọi `handle_turn`, nên Telethon và thoại sau này không phải viết lại agent.

## Điều kiện khép

`recommend_wrap` chỉ đề xuất khép khi đủ cả các điều kiện sau:

- Đã có ít nhất ba lượt trong lịch sử khớp.
- Ba lượt gần nhất không có nhánh `new`.
- Ba lượt cùng một họ kịch bản (`family_id`, hoặc `script_id` nếu không có cha).
- Mỗi lượt có độ tin cậy từ 0.72 trở lên.
- Bước của lượt cuối từ 2 trở lên, không lùi so với lượt đầu cửa sổ, và cửa sổ không đứng yên một bước.

Planner có thể trả `close_polite`. Máy chủ đổi mục tiêu đó thành hỏi tiếp khi `recommend_wrap` chưa cho phép. Jailbreak, hoặc mức nghi từ 0.7, kéo mục tiêu về `feign_confusion` trừ khi kế hoạch đã là giả vờ, móc cảm xúc hoặc trì hoãn.

`AGENT_AGGRESSIVENESS` nhận `cautious`, `normal` hoặc `persistent`. Ở `persistent`, khi không có nhánh mới và không đang bị dò, planner bị đẩy về mục còn thiếu trên bảng khai thác. Hai lượt không có thêm chỉ dấu thì agent hỏi mục còn thiếu (số tài khoản, đường dẫn, ứng dụng, số tiền) thay vì giả vờ rối. Nghi ngờ chỉ làm agent lùi lại khi lượt hiện tại thật sự bị dò.

Đã hỏi danh tính thì playbook của loại lừa đang khớp chuyển sang mục tiếp theo chưa hỏi, ví dụ phí, tài khoản hoặc đường dẫn.

## Nhánh mới

Nhánh mới là hoàn cảnh riêng của persona (con ở xa, sống một mình, shop, học phí) mà kịch bản đang khớp và các biến thể của nó không có. Nếu thư viện đã có biến thể đó, hội thoại báo khớp nhánh đã có và tiếp tục bám nhánh. Nhánh mới cần hai lần cùng một loại trước khi được ghi nhận ổn định.

Khi trích xuất, máy chủ gán quan hệ, không để mô hình tự chọn:

- Có nhánh mới và đang khớp một kịch bản: `variant`, vào hàng chờ, `parent_id` là họ của kịch bản.
- Độ tin cậy lượt cuối từ 0.62 và không có nhánh mới: `duplicate`, gộp câu mới vào bản đã xuất bản, tăng `occurrence_count`.
- Còn lại: `new_root`, vào hàng chờ như kịch bản mới.

Duyệt (`POST /api/moderation/{id}/approve`) đặt `published` và gắn embedding. Từ chối đặt `rejected`. Nếu duyệt một biến thể, chỉ dấu của nó được gộp vào kịch bản cha.

## An toàn đầu ra

`inspect_outbound` là quyền phủ quyết. Vi phạm cứng gồm nhận chuyển hoặc nạp tiền, nhận đã cài, nhận chia OTP, cam kết một hành động đã xong, nhận là AI, hỗ trợ gây hại, giọng chuyên gia kết thúc cuộc thoại, và một số không có trong hồ sơ giả.

`critique_reply` lập ghi chú cho đúng một lần viết lại: nhận trả tiền, nhận đã cài, nhận là máy, dạy đời, sai cặp đại từ hoặc giọng tao/mày, thiếu câu hỏi khi đang khai thác, lặp câu mở. Guard bắt đầu ngay khi có câu nháp. Lần viết lại chạy cạnh lần duyệt đó. Nếu câu viết lại ít lỗi hơn, guard duyệt lại câu mới.

Model có thể đề xuất `safe_reply`. Câu đó chỉ được gửi khi khác bản nháp và chính luật không còn thấy vi phạm. Sai đại từ có thể được sửa tại chỗ nếu câu sửa sạch. Mọi đường còn lại dùng `fallback_reply`, một câu an toàn trong vai. Guard hết giờ thì lượt giữ câu trong vai và không gửi bản nháp. Một lần thử guard nền có thể ghi nhận cho lượt sau. Lượt đó đã giữ câu rồi.

OTP gửi đi, khi mục tiêu là đọc mã, là mã giả sáu số từ id cuộc thoại. Số trong hồ sơ giả của persona được coi là số được phép nhắc.

## Tìm thư viện và embedding

`search_scripts` trộn điểm. Khi có vector: 0.48 cosine đã co + 0.30 từ khóa + 0.22 điểm bước. Khi chưa có vector: 0.62 từ khóa + 0.38 điểm bước. Thương hiệu xuất hiện trong tin được cộng 0.08. Trên Postgres, vector nằm ở cột `embedding_vec`. Test SQLite tính cosine trong Python.

Cuộc thoại đang bám một kịch bản (`prefer_ids` là id và họ của lượt trước) thì giữ kịch bản đó, trừ khi kịch bản khác hơn ít nhất 0.22 điểm.

Với `text-embedding-3-small`, cosine được co về 0–1 trước khi trộn: `(cos - 0.28) / 0.5`. Sàn 0.28 và bề rộng 0.5 là mặc định của đường 9router. Đặt `EMBED_COS_FLOOR` và `EMBED_COS_SPAN` nếu muốn số khác. Sàn mặc định trong config là `-1`, nghĩa là dùng sàn của nhà cung cấp.

`EMBED_PROVIDER=auto` dùng 9router khi có khóa router, không thì Gemini `gemini-embedding-001`, 768 chiều. `none` chỉ tìm theo từ khóa. Vector của hai model không trộn: router lỗi thì tìm theo từ khóa, không đổi sang model embedding khác, trừ khi `MODEL_EMBED_FALLBACK` được đặt và cùng không gian vector.

Đổi `MODEL_EMBED` thì app gắn lại embedding lúc khởi động cho bản đã xuất bản còn lệch model. Gắn lại tay:

```bash
cd backend && python -m app.reembed
cd backend && python -m app.reembed --all
```

`--all` xóa embedding cũ rồi gắn lại.

## Failover mô hình

`LLM_PROVIDER=auto` và `openai-compatible` gọi router trước, Gemini khi chuỗi router lỗi. `gemini` đảo thứ tự. Không có khóa nào thì `MockProvider`.

Trong một vai, router nhận `response_format: json_schema`. Hết giờ khoảng năm giây mà model chính còn im thì model dự phòng của vai được gọi song song, lấy câu phân tích được trước. Lỗi JSON hoặc HTTP thì đổi sang model dự phòng, không gọi lại cùng id. Cả hai thất bại thì `FallbackProvider` sang Gemini. `gemini-2.5-flash-lite` bị chặn vì API trả 404 và bị đổi về `gemini-2.5-flash`. Gemini chat dùng `v1beta`. Mọi request router có `User-Agent: honeypot/1.0`.

Trần từng vai nằm ở `config.py` và bảng trong README. Nếu lần chính im khoảng năm giây, lần đổi chạy song song và không dùng nốt đồng hồ của lần chính. Cả lượt honeypot dừng ở `TURN_DEADLINE` (mặc định 25 giây), gồm analyst, planner, persona, viết lại và guard.

## Luyện tập

`backend/app/api/training.py` khai báo các route không tạo `Script` và không tạo chỉ dấu. Điểm là `score_session`: từ 80 là «Tỉnh táo», từ 50 là «Cần cẩn thận», dưới đó là «Đã sập bẫy».

Kết thúc an toàn khi báo công an, chặn máy, hai lượt từ chối liên tiếp, hoặc vừa từ chối vừa xác minh. Độ khó Dễ kết thúc ngay sau một lượt từ chối hoặc xác minh. `fell` và `leak` kết thúc `scammed`. Hết lượt thì `timeout`. Nút gác máy, xác minh kênh chính thức và báo cáo là hành động riêng, không cần mô hình.

`sanitize_scammer_text` thay đường dẫn, email, tên miền, file `.apk`, ID điều khiển và số dài. Cụm tiền ngắn và mốc thời gian ngắn được giữ. Câu còn hướng dẫn bật quyền hoặc quét khuôn mặt thì bị bỏ. `_is_tutor_voice` loại câu mang từ cảnh báo, xin lỗi, hoặc nhận là AI.

`mask_user_text` chạy trước khi lưu lời người chơi. Một số người chơi đang đòi từ phía kia thì không bị coi là đưa số của mình.

Nhóm luyện tập map từ `category` của kịch bản:

| Nhóm | Category |
| --- | --- |
| Công an / cơ quan giả | police, vneid, tax |
| Ngân hàng và ví giả | bank, momo, telco, utility |
| Giao hàng / sàn | shipper, ecommerce |
| Việc làm online | job, course |
| Đầu tư và tình cảm | investment, romance, recovery |
| Mã QR | qr |
| Deepfake / người thân | deepfake, relative, hijack |
| Cài app chiếm quyền | rat |
| Khác | prize, loan, charity, rental, travel, other |

## Chỉ dấu và kiểm tra tin

Mỗi lượt honeypot thu số điện thoại, số tài khoản, URL (kể cả tên miền trần), tên app, ví và ID điều khiển vào hồ sơ vụ. Mạng lưới ở `/phan-tich/mang-luoi` đọc chỉ dấu của bản `published` và `pending`.

`POST /api/check` chấm điểm bằng mô hình khi có khóa, và vẫn trả điểm tất định khi mô hình lỗi. Tin OTP, tiền điện, giao hàng hoặc khuyến mãi từ kênh quen, nếu không kèm yêu cầu mạnh, ở mức thấp. Hai chỉ dấu mạnh trở lên không bị gán nhãn thấp.

Trang chủ còn tra số, tài khoản và đường dẫn qua `/api/intel/lookup`.
