import json
from pathlib import Path

from scripts.import_public_datasets import parse_huggingface_csv, parse_kaggle_jsonl


def test_parsers_keep_only_scam_rows(tmp_path: Path):
    csv_path = tmp_path / "full_dataset.csv"
    csv_path.write_text(
        "message_id,date,message,label\n"
        "A1,01/01/2026,Vi cua ban bi khoa,1\n"
        "A2,01/01/2026,Ma OTP giao dich,0\n",
        encoding="utf-8",
    )
    parsed = parse_huggingface_csv(csv_path)
    assert len(parsed) == 1
    assert parsed[0]["external_id"] == "A1"

    jsonl = tmp_path / "vi_fraud_pool.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps({"id": "k1", "source": "core_scam", "text": "nop phi nhan giai", "y": 1, "group": "g1"}),
                json.dumps({"id": "k2", "source": "core_harmless", "text": "hop thu", "y": 0, "group": "g2"}),
            ]
        ),
        encoding="utf-8",
    )
    kaggle = parse_kaggle_jsonl(jsonl)
    assert len(kaggle) == 1
    assert kaggle[0]["group"] == "g1"
