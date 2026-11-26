# Triển khai

Giám khảo cần một URL sống tới 11/12/2026. Cách ít phụ thuộc nền tảng nhất là một VPS với Docker.

```bash
git clone <repo>
cp .env.example .env
# điền LLM_API_KEY hoặc OPENAI_API_KEY, GEMINI_API_KEY, và ADMIN_TOKEN
docker compose up -d --build
```

Mở cổng 4178, hoặc sửa Compose để `honeypot-web` nghe cổng 80. Dữ liệu nằm ở volume `pgdata`. Cập nhật: `git pull && docker compose up -d --build`.

Biến nào Compose thực sự chuyển vào API nằm ở [bien-moi-truong.md](bien-moi-truong.md).

## Không dùng Docker

Chỉ để phát triển. Demo chấm nên đi Compose.

```bash
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cd ../frontend && npm install
```

Một terminal: `uvicorn app.main:app --app-dir backend --port 8091`, với `DATABASE_URL` trỏ Postgres có extension `vector`. Terminal kia: `npm run dev --prefix frontend` (Vite cổng 4178, proxy `/api`). SQLite chỉ dùng cho pytest và cho eval khi không đặt `DATABASE_URL`.

## Demo giám khảo

Mở `/phan-tich/demo` và bấm **Bắt đầu demo**. Người xem đóng vai người gọi. Agent là bà Nguyễn Thị Năm. Bấm «Tự đi nốt các câu gợi ý», rồi trích xuất. Chuyện con ở Đức là nhánh thư viện đã có. Việc bà sống một mình là nhánh mới, nên hồ sơ vào hàng chờ. Duyệt ở `/phan-tich/kiem-duyet` thì bản đó được xuất bản. Trang còn một demo thứ hai: ông Sáu bị ép cài app Dịch vụ công giả.

Bật **Luận giải của agent** trong phòng hội thoại để xem JSON của phân tích, kế hoạch và lớp an toàn từng lượt. Banner khóa model và embedding chỉ hiện trong Phòng phân tích.

Đường cũ chuyển hướng: `/kiem-tra` về trang chủ, `/thu-vien` về tab kịch bản của Cảnh báo, `/hoi-thoai`, `/mang-luoi`, `/kiem-duyet` và `/demo` vào Phòng phân tích.

## Render

`render.yaml` khai hai service Docker và một Postgres. Sau khi có DB, chạy `CREATE EXTENSION IF NOT EXISTS vector;` nếu gói cho phép. `DATABASE_URL` dạng `postgres://` được chuẩn hóa trong `backend/app/database.py`. Đặt `GEMINI_API_KEY` và khóa router. Nếu Postgres của Render không có pgvector, dùng VPS.

## Railway

Hai service từ `backend/Dockerfile` và `frontend/Dockerfile`, cộng plugin Postgres. Biến giống `.env.example`, và chỉ những biến khai trong Compose mới có mặt nếu bạn copy nguyên khối đó. Service web không cần URL API công khai vì nginx trong image proxy `/api` tới hostname `honeypot-api`. Đặt tên service API là `honeypot-api`, hoặc sửa `frontend/nginx.conf` cho đúng hostname nội bộ rồi build lại.

## Fly

`fly.toml` là app API, region `sin`, không tự tắt máy. Tạo Postgres từ image có pgvector, rồi:

```bash
fly secrets set GEMINI_API_KEY=... DATABASE_URL=postgresql+psycopg://... ADMIN_TOKEN=...
fly deploy
```

App web là Fly app thứ hai, build `frontend/Dockerfile`. Hai app không chung mạng Docker, nên `honeypot-api:8000` trong `frontend/nginx.conf` không chạy trên Fly. Trỏ nginx tới URL công khai của API rồi build, hoặc phục vụ cả hai bằng Compose trên một máy.

## Nhập dữ liệu công khai

`backend/scripts/import_public_datasets.py` đọc hai nguồn được nêu trong đề bài. Script không tải và không commit dữ liệu lớn. `--load` mới đưa hàng vào hàng chờ, và chỉ tới `--limit`.

- Hugging Face `trannguyenthaituan/vietnamese_sms_dataset`, file `full_dataset.csv`: `message_id`, `date`, `message`, `label`.
- Kaggle `ngovanhh/vi-fraud-bench-vi`, file `vi_fraud_pool.jsonl`: `id`, `source`, `text`, `y`, `group`.

```bash
cd backend
python scripts/import_public_datasets.py --source huggingface --path ./full_dataset.csv
python scripts/import_public_datasets.py --source kaggle --path ./vi_fraud_pool.jsonl --load --limit 40
```

`--download` với Hugging Face cần `pip install huggingface_hub`. Kaggle tải bằng CLI và tài khoản của bạn.
