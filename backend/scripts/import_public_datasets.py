"""Import public Vietnamese scam text into the moderation queue.

Nothing is downloaded unless you pass --download, and nothing large is written
into git. Two sources, named in the contest brief:

- Hugging Face `trannguyenthaituan/vietnamese_sms_dataset`
  `full_dataset.csv`: message_id, date, message, label (1 = scam / spam).
- Kaggle `ngovanhh/vi-fraud-bench-vi`
  `vi_fraud_pool.jsonl`: id, source, text, y (1 = scam), group.

Rows become pending library items with source type `news` only when you pass
--load, and only up to --limit so a 30k file does not flood the queue.

Examples:

    python scripts/import_public_datasets.py --source huggingface --path ./full_dataset.csv
    python scripts/import_public_datasets.py --source kaggle --path ./vi_fraud_pool.jsonl --load --limit 40
    python scripts/import_public_datasets.py --source huggingface --download
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "imports"
sys.path.insert(0, str(ROOT))


def parse_huggingface_csv(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            label = str(record.get("label", "")).strip()
            if label not in {"1", "spam", "scam"}:
                continue
            text = (record.get("message") or record.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "external_id": record.get("message_id") or record.get("id") or "",
                    "text": text,
                    "source": "huggingface:trannguyenthaituan/vietnamese_sms_dataset",
                    "group": "",
                }
            )
    return rows


def parse_kaggle_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if int(record.get("y", 0)) != 1:
                continue
            text = (record.get("text") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "external_id": str(record.get("id") or ""),
                    "text": text,
                    "source": f"kaggle:vi-fraud-bench-vi:{record.get('source') or 'pool'}",
                    "group": str(record.get("group") or ""),
                }
            )
    return rows


def download(source: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    if source == "huggingface":
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise SystemExit("Cài huggingface_hub rồi chạy lại: pip install huggingface_hub") from exc
        saved = hf_hub_download(
            repo_id="trannguyenthaituan/vietnamese_sms_dataset",
            filename="full_dataset.csv",
            repo_type="dataset",
            local_dir=CACHE / "hf",
        )
        return Path(saved)
    if source == "kaggle":
        raise SystemExit(
            "Tải Kaggle bằng tài khoản của bạn, không nhúng khóa vào repo:\n"
            "  pip install kaggle && kaggle datasets download -d ngovanhh/vi-fraud-bench-vi -p .cache/imports\n"
            "Giải nén và truyền --path tới vi_fraud_pool.jsonl."
        )
    raise SystemExit(f"Nguồn không hỗ trợ: {source}")


def load_rows(rows: list[dict], limit: int) -> int:
    import os

    os.environ.setdefault("LLM_PROVIDER", "mock")
    from app.config import get_settings
    from app.database import init_database, make_engine, make_session_factory
    from app.models import Script, utcnow

    get_settings.cache_clear()
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_database(engine)
    factory = make_session_factory(engine)
    inserted = 0
    with factory() as session:
        for index, row in enumerate(rows[:limit]):
            script_id = f"imp-{row['source'].split(':')[0]}-{row['external_id'] or index}"[:64]
            if session.get(Script, script_id) is not None:
                continue
            session.add(
                Script(
                    id=script_id,
                    parent_id=None,
                    title=f"Tin nhắn thô {row['external_id'] or index}",
                    category="other",
                    channel="sms",
                    brand="",
                    summary=row["text"][:500],
                    steps=[{"actor": "scammer", "intent": "Tin nhắn đơn lẻ, chưa phải kịch bản đủ bước", "phrases": [row["text"][:240]]}],
                    hooks=[],
                    red_flags=["Bản nhập từ dữ liệu công khai, cần người duyệt gắn vào kịch bản."],
                    advice="Không bấm liên kết, không đọc OTP, không chuyển tiền theo tin nhắn này.",
                    sources=[{"type": "news", "ref": row["source"], "external_id": row["external_id"], "group": row["group"]}],
                    first_seen=utcnow(),
                    last_seen=utcnow(),
                    occurrence_count=1,
                    status="pending",
                    novelty_note="Nhập từ bộ dữ liệu công khai, chưa phải kịch bản đã biên tập.",
                )
            )
            inserted += 1
        session.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhập bộ dữ liệu lừa đảo công khai vào hàng chờ duyệt.")
    parser.add_argument("--source", choices=("huggingface", "kaggle"), required=True)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--load", action="store_true", help="Ghi vào hàng chờ duyệt, tối đa --limit dòng.")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    path = args.path
    if args.download:
        path = download(args.source)
    if path is None:
        raise SystemExit("Cần --path hoặc --download.")
    rows = parse_huggingface_csv(path) if args.source == "huggingface" else parse_kaggle_jsonl(path)
    print(f"{len(rows)} dòng lừa đảo / rác từ {path}.")
    if args.load:
        print(f"Đã đưa {load_rows(rows, args.limit)} dòng vào hàng chờ (tối đa {args.limit}).")
    else:
        print("Chưa ghi cơ sở dữ liệu. Thêm --load khi muốn đưa một mẫu vào hàng chờ.")


if __name__ == "__main__":
    main()
