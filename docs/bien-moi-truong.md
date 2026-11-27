# Biến môi trường

Mặc định lấy từ `backend/app/config.py`. `.env.example` liệt kê các biến thường sửa khi chạy thật. Không ghi khóa thật vào repo. Để trống khóa thì API chạy `MockProvider` và giao diện hiện banner mô phỏng.

`docker compose` chỉ đưa vào container `honeypot-api` các biến có mặt trong khối `environment` của `docker-compose.yml`: khóa, `OPENAI_BASE_URL`, `OPENAI_MODEL`, sáu model vai chính, `MODEL_SIM_FALLBACK`, `TIMEOUT_SIM`, `TIMEOUT_SIM_FALLBACK`, `LLM_PROVIDER`, các biến Gemini, và `ADMIN_TOKEN`. Biến không nằm trong khối đó dùng mặc định của `config.py` bên trong image, kể cả khi đã sửa trong `.env` trên máy host. `DATABASE_URL` trong Compose trỏ tới `honeypot-db:5432`, không dùng URL localhost của file `.env`.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `LLM_API_KEY` | trống | Khóa router. `OPENAI_API_KEY` được dùng khi biến này trống |
| `OPENAI_API_KEY` | trống | Bí danh của khóa router |
| `OPENAI_BASE_URL` | `https://rm7g66d.abc-tunnel.us/v1` | Router tương thích OpenAI (9router) |
| `OPENAI_MODEL` | `cx/gpt-6-luna` | Model khi một biến vai để trống |
| `MODEL_PERSONA` | `cx/gpt-6-luna` | Giọng nạn nhân |
| `MODEL_ANALYST` | `ag/gemini-4-hydrogen-low` | Phân tích lượt, và chấm nhãn luyện tập khi luật còn trung tính |
| `MODEL_PLANNER` | `ag/gemini-3.8-flash-low` | Chọn mục tiêu lượt kế |
| `MODEL_GUARD` | `ag/gemini-3.8-flash-low` | Duyệt câu trước khi gửi |
| `MODEL_EXTRACT` | `cx/gpt-5.6-luna` | Trích kịch bản cuối hội thoại |
| `MODEL_SIM` | `ag/gemini-3.8-flash-low` | Giọng người lừa trong bài luyện |
| `MODEL_PERSONA_FALLBACK` | `cx/gpt-5.6-luna` | Một lần đổi vai. Trùng model chính thì bỏ qua |
| `MODEL_ANALYST_FALLBACK` | `ag/gemini-3.8-flash-low` | Như trên |
| `MODEL_PLANNER_FALLBACK` | `cx/gpt-5.6-luna` | Như trên |
| `MODEL_GUARD_FALLBACK` | `cx/gpt-5.6-luna` | Như trên |
| `MODEL_EXTRACT_FALLBACK` | `cx/gpt-6-luna` | Như trên |
| `MODEL_SIM_FALLBACK` | `cx/gpt-5.6-luna` | Cổng khác model chính của `sim` |
| `TIMEOUT_PERSONA` | 12 | Giây, lần gọi chính |
| `TIMEOUT_ANALYST` | 18 | Giây |
| `TIMEOUT_PLANNER` | 18 | Giây |
| `TIMEOUT_GUARD` | 9 | Giây |
| `TIMEOUT_EXTRACT` | 30 | Giây |
| `TIMEOUT_SIM` | 7 | Giây. Hết giờ thì câu mẫu đã lọc |
| `TIMEOUT_PERSONA_FALLBACK` | 10 | Ngân sách riêng cho lần đổi, không dùng nốt đồng hồ lần chính |
| `TIMEOUT_ANALYST_FALLBACK` | 12 | Giây |
| `TIMEOUT_PLANNER_FALLBACK` | 12 | Giây |
| `TIMEOUT_GUARD_FALLBACK` | 7 | Giây |
| `TIMEOUT_EXTRACT_FALLBACK` | 20 | Giây |
| `TIMEOUT_SIM_FALLBACK` | 5 | Giây |
| `TURN_DEADLINE` | 25 | Trần cả lượt honeypot, gồm sửa JSON và đổi model |
| `GUARD_SKIP_PLAIN` | `true` | Bỏ qua guard model với câu ngắn mà luật thấy sạch và không chạm tiền, mã, app, link, giấy tờ hay chuyện máy. `false` để luôn gọi guard |
| `ANALYST_GRACE` | 1.0 | Giây analyst được chạy quá planner. Quá mức này lượt đi tiếp theo khớp thư viện, ghi chú của analyst được ghép vào hồ sơ nếu kịp. `0` để đợi đủ |
| `LLM_PROVIDER` | `auto` | `auto` hoặc `openai-compatible`: router rồi Gemini. `gemini`: ngược lại. `mock`: test và demo không khóa |
| `GEMINI_API_KEY` | trống | Khóa Google AI Studio. Chat dự phòng, và embedding khi không đi router |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Chat Gemini. `gemini-2.5-flash-lite` bị từ chối vì 404 |
| `GEMINI_MODEL_PREFERRED` | trống | Thử trước, ví dụ `gemini-3.5-flash`. 503, timeout hoặc 404 thì về `GEMINI_MODEL` |
| `GEMINI_MODEL_FALLBACK` | `gemini-2.5-flash` | Model Gemini cuối cùng |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | Khi embedding đi Gemini. 768 chiều, chuẩn hóa |
| `EMBED_PROVIDER` | `auto` | `auto`: 9router nếu có khóa router, không thì Gemini. `9router`, `gemini`, hoặc `none` (chỉ từ khóa) |
| `MODEL_EMBED` | `openrouter/openai/text-embedding-3-small` | Gửi `dimensions=768` |
| `MODEL_EMBED_FALLBACK` | trống | Chỉ đặt model cùng không gian vector. Trống thì router lỗi sẽ tìm theo từ khóa |
| `TIMEOUT_EMBED` | 6 | Giây cho một câu. Lô gắn lại được chờ lâu hơn |
| `EMBED_COS_FLOOR` | -1 | Sàn cosine trước khi trộn điểm. `-1` dùng sàn của nhà cung cấp (0.28 với text-embedding-3) |
| `EMBED_COS_SPAN` | -1 | Bề rộng cosine. Giá trị không dương dùng bề rộng của nhà cung cấp (0.5 với text-embedding-3) |
| `AGENT_AGGRESSIVENESS` | `normal` | `cautious`, `normal`, hoặc `persistent` |
| `ADMIN_TOKEN` | trống | Nếu đặt, hàng chờ cần header `X-Admin-Token`. Trống thì cửa demo mở |
| `DATABASE_URL` | `postgresql+psycopg://gianan:gianan@localhost:5433/gianan` | `postgres://` và `postgresql://` của Render hoặc Railway được đổi sang driver psycopg |
| `LOG_LEVEL` | `INFO` | Mức log |

Đổi `MODEL_EMBED` thì app gắn lại embedding lúc khởi động. Gắn lại tay: `cd backend && python -m app.reembed`, thêm `--all` để xóa rồi gắn lại. Xem [kien-truc-chi-tiet.md](kien-truc-chi-tiet.md).
