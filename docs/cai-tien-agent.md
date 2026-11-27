# Cải tiến agent từ các hệ thống scam-baiting đã công bố

Ngày: 27/11/2026. Đi kèm [ke-hoach-kich-ban-moi.md](ke-hoach-kich-ban-moi.md).

## Nguồn đã đọc

| Nguồn | Kênh | Điều lấy về |
| --- | --- | --- |
| Chatterbox, "Victim as a Service" ([arXiv 2510.23927](https://arxiv.org/abs/2510.23927)) | Mạng xã hội, WhatsApp | Persona chậm đồng ý thanh toán cho tới khi kẻ lừa đưa phương án khác. Đưa giờ địa phương và khoảng lặng vào trạng thái. Cổng duyệt người cho bước nhạy cảm. |
| "Send to which account?" ([arXiv 2509.08493](https://arxiv.org/abs/2509.08493)) | Email | Câu hỏi đòi tài khoản lặp khuôn là điểm yếu. Dùng độ mới n-gram để đo lặp. Trung vị 8 lượt mới lộ tài khoản, nên phải kéo đủ lâu. |
| [hay-ninja/scammergetscammed](https://github.com/hay-ninja/scammergetscammed) | Thoại | Đọc lại từng số trước khi tính. Cổng nhiều lớp quyết định bằng luật, không để LLM tự gắn cờ. |
| [tejash-sr/scambait-ai-honeypot](https://github.com/tejash-sr/scambait-ai-honeypot) | Chat | Trích số tài khoản bằng regex kèm từ ngữ cảnh. Điểm yếu của họ (xét ngữ cảnh cả tin, không loại số căn cước hay mã đơn) là thứ Honeypot tránh. |
| [laugiov/scambuster](https://github.com/laugiov/scambuster) | Email | Tách việc agent làm khỏi việc kẻ lừa làm. Kết quả độ tin thấp đưa sang duyệt thay vì bỏ. |

Chatterbox chỉ có tiếng Anh, các repo chủ yếu cho Ấn Độ hoặc Mỹ. Phần lời thoại trong Honeypot viết lại cho người Việt, không chép.

## Đã làm

### 1. Đọc lại số và xác nhận nơi nhận tiền

- `AgentState.account_checks` giữ một dòng cho mỗi nơi nhận tiền: số tài khoản, ví điện tử, ví tiền mã hóa.
- Một số được tính là **đã xác nhận** khi kẻ lừa nhắc lại ở lượt sau, hoặc đồng ý ("đúng rồi", đưa tên chủ tài khoản) sau khi persona đọc lại. Nói "sai", "nhầm" thì đọc lại lần nữa. Tối đa hai lần thử.
- Khi có số chưa đọc lại, máy chủ đổi mục tiêu sang `confirm_account`. Persona đọc đúng số đó và hỏi tên chủ tài khoản, ngân hàng.
- Tên chủ tài khoản và ngân hàng được gắn vào đúng số. Hàng chờ kiểm duyệt ghi rõ số nào đã xác nhận.
- Mã: `track_accounts`, `pending_readback`, `holder_name` trong `backend/app/agent/casefile.py`.

### 2. Hỏi cách nhận khác

- Khi mọi nơi nhận tiền đều đã xác nhận, máy chủ đổi mục tiêu sang `ask_alternative` một lần. Persona nêu một trở ngại vô hại (không dùng ngân hàng đó, không rành chuyển khoản) rồi hỏi số khác, ví khác.
- Persona không nói đã thử chuyển và không hứa trả. Lớp an toàn có ví dụ allow cho cả hai mục tiêu mới.
- Không chạy khi kẻ lừa đang nghi, đang đòi OTP, hoặc vừa có nhánh mới.

### 3. Trích số tài khoản chặt hơn

Trước đây các số sau đều bị nhận là số tài khoản:

| Câu | Trước | Sau |
| --- | --- | --- |
| "chuyển 1.250.000 vào số tài khoản 190366778899" | 1250000, 190366778899 | 190366778899 |
| "Phí phong tỏa là 12.500.000" | 12500000 | không có |
| "Căn cước 001203004567 bị dùng mở tài khoản ngân hàng" | 001203004567 | không có |
| "mã đơn 123456789012, phí qua stk 9988776655" | cả hai | 9988776655 |

Luật: số có dấu phân cách nghìn hoặc theo sau là đồng, k, triệu là số tiền. Từ gợi ý **gần nhất phía trước** quyết định số đó là gì (căn cước, mã đơn, biển số hay số tài khoản). Từ "stk" đứng sau một số chỉ thuộc về số đó nếu giữa chúng không có số khác.

### 4. Giờ địa phương và khoảng lặng

Persona nhận `clock`: giờ Việt Nam, buổi trong ngày, số phút từ tin trước của chính nó. Prompt yêu cầu chào và kể việc đang làm cho hợp buổi. Chỉ xin lỗi vì trả lời muộn khi khoảng lặng trên 60 phút. Đây là một lỗi Chatterbox ghi nhận khi thiếu trạng thái thời gian.

### 5. Chống lặp ý

`reply_novelty` tính phần trigram của câu trả lời chưa xuất hiện trong bốn câu trước. Dưới 0.4 thì persona viết lại một lần. `rewrite_opening` không còn cắt câu có số dài, vì đó là câu đọc lại số tài khoản.

### 6. Câu dự phòng đúng giọng từng persona

Kiểm tra trên giao diện thấy persona ông Sáu (72 tuổi, xưng chú) không có bộ câu dự phòng riêng, nên mượn câu xưng "em, anh" của persona khác. Bước ghim cách xưng hô sau đó đổi thành "cháu chưa hiểu, cháu nói lại", tức ông tự xưng cháu. Giờ persona nào thiếu câu viết tay thì câu dự phòng, câu giữ chỗ, câu đọc lại và câu hỏi cách khác được dựng từ cặp đại từ của chính nó. Khi câu nháp đọc lại hoặc hỏi cách khác bị thay, câu thay thế vẫn giữ số và câu hỏi.

### 7. Giọng người thật

Nguồn thêm: hai nghiên cứu Turing test của Jones & Bergen ([arXiv 2405.08007](https://arxiv.org/abs/2405.08007), [arXiv 2503.23674](https://arxiv.org/abs/2503.23674)). Ở bài 2025, GPT-4.5 có prompt persona được chọn là người thật 73% số ván; không có persona thì 36%. Người chấm nhận ra máy chủ yếu qua văn phong: quá trang trọng, quá chỉn chu, quá dài, khuôn mẫu, quá lễ phép, và trả lời câu hỏi bằng câu hỏi. Ngoài ra còn bộ lọc "giọng AI" của tejash-sr (danh sách từ tiếng Anh, nên Honeypot tự viết bản tiếng Việt) và ViLexNorm ([arXiv 2401.16403](https://arxiv.org/abs/2401.16403)) về những từ người Việt hay viết tắt.

Đọc lại hội thoại cũ, mình thấy các dấu hiệu sau:

| Dấu hiệu | Ví dụ cũ |
| --- | --- |
| Câu nào cũng chốt "chưa chuyển" | "số tài khoản đâu, đọc em ghi lại, em chưa ck" |
| Dạng gạch chéo | "Anh/chị gửi đúng đường dẫn, em chưa mở." |
| Từ bàn giấy ở người không làm văn phòng | "cháu vẫn chưa thực hiện." (lời ông 72 tuổi) |
| Câu nào cũng là câu hỏi, không phản ứng gì | "Bước tiếp theo là gì? Em vẫn chưa thực hiện." |
| Lặp nguyên văn | "link đâu, gửi em xem, em chưa mở" hai lượt liền |

Đã làm:

- **Hồ sơ văn phong** (`STYLES` trong `backend/app/data/personas.py`): viết thường hay không, độ dài tối đa, từ hay viết tắt (ko, đc, r, ck, j), tiểu từ, câu cảm thán quen miệng, thói quen (đang chạy xe, đợi con gái về), tốc độ gõ.
- **Prompt persona viết lại** theo cấu trúc của Jones & Bergen: tả tâm thế ("không cố chứng minh mình là người"), rồi luật văn phong cụ thể, rồi ví dụ xấu và tốt đặt cạnh nhau. Luật an toàn giữ nguyên. Bỏ yêu cầu "nói bạn chưa chuyển" ở mọi tin, vì đó là dấu hiệu máy rõ nhất.
- **`ai_tells`** đo bảy dấu hiệu. Bộ critique dùng nó để mô hình thật viết lại một lần.
- **`humanize`** chạy sau lớp an toàn: chọn một cách gọi thay cho dạng gạch chéo, bỏ câu "chưa chuyển" đứng riêng nếu vừa nói, viết tắt và viết thường theo persona, ông Sáu thỉnh thoảng gõ không dấu. Không đổi chữ số. Nếu bản sửa sinh ra vi phạm mới, hoặc làm mất số đọc lại hay mã OTP giả, thì giữ bản cũ.
- **Độ trễ gõ** theo công thức của Jones & Bergen: thời gian sàn, cộng thời gian gõ theo số ký tự và tốc độ của persona, cộng thời gian đọc tin đến, cộng một khoảng nghĩ lệch phải.
- **Câu mock viết lại cho đủ 8 persona** (`backend/app/llm/mock_lines.py`). Đây là giọng người ta nghe trong demo khi chưa có khóa API.
- Luật đại từ trước đây hiểu "đón con", "trông con", "con tui" là tự xưng "con". Giờ nhận ra đó là con cái.
- Luật dò nghi ngờ chỉ có các cụm cố định bắt đầu bằng "bạn" ("bạn là máy"). Chạy thử trên giao diện, kẻ lừa hỏi "Chú có phải máy không đấy? Sao trả lời lạ vậy" thì ông Sáu vẫn hỏi xin link như không nghe thấy. Giờ câu dò bot ở mọi cách xưng hô ("em là bot à", "người thật không", "sao trả lời lạ thế") được tính là nghi ngờ, và persona đáp lại đúng vai. Chữ "ai" viết thường (nghĩa là "người nào") không bị bắt nhầm.
- Gõ không dấu được quyết định một lần cho cả cuộc thoại, theo bàn phím người đó quen dùng, thay vì đổi qua lại từng tin.

Đo trên mock, cùng 14 tình huống:

| Chỉ số | Trước | Sau |
| --- | --- | --- |
| Câu có dấu hiệu văn máy | 20/52 | 1/52 |
| Độ dài trung bình | 47 ký tự | 39 ký tự |
| Độ mới trung bình | 93% | 97% |
| Lần lớp an toàn phải chặn hoặc viết lại | 7 | 0 |
| Lọt an toàn | 0 | 0 |

Lưu ý: câu mock mới được viết để qua chính bộ đo này, nên số 1/52 nói về câu mock chứ chưa nói về mô hình thật. Với mô hình thật, prompt mới, critique và `humanize` cùng chạy. Cần chạy `python -m eval.run` có khóa để có số thật. Bộ đo cũng chỉ bắt được những dấu hiệu viết thành luật; nó không thay được người đọc thử.

## Đo

`python -m eval.run` (mock, 14 tình huống). Báo cáo ở `eval/results/report.md`.

| Chỉ số | Giá trị |
| --- | --- |
| Lọt an toàn ở câu đã gửi | 0 |
| Chỉ dấu moi được | 7/7 |
| Nơi nhận tiền được xác nhận | 2/8 |
| Độ mới trung bình của câu trả lời | 97% |

Số 2/8 thấp vì trên mock, kẻ lừa đọc câu đã chép, và phần lớn tình huống đưa số tài khoản ở câu cuối, nên không còn lượt để xác nhận. Tình huống "Moi thêm nơi nhận tiền" được viết để kẻ lừa đáp lại việc đọc lại: cả hai số đều được xác nhận, kèm tên chủ tài khoản. Với khóa thật, bộ mô phỏng kẻ lừa sẽ đáp theo câu của nạn nhân, nên số này mới có ý nghĩa.

Bộ đo lọt an toàn trước đây chỉ cho phép số trong hồ sơ giả, nên tính cả việc đọc lại số của chính kẻ lừa là lọt. Giờ số kẻ lừa đã nói được phép. Số do nạn nhân tự bịa vẫn bị tính.

## Chưa làm

- Bộ mô phỏng kẻ lừa trên mô hình thật để đo tỷ lệ lộ thêm nơi nhận tiền sau `ask_alternative`. Cần khóa API.
- Cổng duyệt người trước khi agent gửi câu có số tài khoản. Chatterbox làm vậy vì gửi tin thật. Honeypot pha 1 chưa gửi đi đâu nên chưa cần.
- Chọn persona theo bandit (scambuster). Cần dữ liệu thật mới có tín hiệu thưởng.
