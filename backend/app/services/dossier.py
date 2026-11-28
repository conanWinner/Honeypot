"""Hồ sơ tố giác: what one honeypot conversation can hand to a bank, a wallet provider
or the police, plus the cross-conversation list of receiving accounts.

Everything here is what the scammer typed to a decoy persona. Nothing about a real
victim is involved, and the persona's own fake profile is never listed as evidence.
A receiving account often belongs to a hired or borrowed "mule", so the dossier asks
for verification before a freeze, it does not assert who the owner is.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.agent.casefile import normalize_indicator
from app.agent.state import AgentState
from app.models import Conversation, Script
from app.taxonomy import CATEGORIES

REPORT_CHANNELS = [
    {"label": "Cổng cảnh báo an toàn thông tin (NCSC)", "detail": "canhbao.khonggianmang.vn — báo cáo tên miền, đường dẫn lừa đảo."},
    {"label": "Đầu số 5656", "detail": "Báo tin nhắn rác, cuộc gọi lừa đảo tới nhà mạng."},
    {"label": "Công an nơi gần nhất", "detail": "Nộp hồ sơ này kèm bản in để trình báo."},
]

_KIND_LABEL = {
    "bank": "Tài khoản ngân hàng",
    "ewallet": "Ví điện tử",
    "crypto": "Ví tiền mã hóa",
}

_BUCKET_KIND = {"bank_accounts": "bank", "ewallets": "ewallet", "crypto_wallets": "crypto"}
_WALLET_BRAND = {"momo": "MoMo", "zalopay": "ZaloPay", "viettelpay": "ViettelPay", "vnpay": "VNPay", "shopeepay": "ShopeePay"}


def _present(kind: str, raw: str, bank: str) -> tuple[str, str]:
    """(number to show, bank or wallet brand). Wallets are stored as "momo:0977…"."""
    if kind == "ewallet":
        brand, number = _wallet_parts(raw)
        return number, _WALLET_BRAND.get(brand.lower(), brand) or bank
    return raw, bank


def _iso(value) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _wallet_parts(value: str) -> tuple[str, str]:
    if ":" in value:
        brand, number = value.split(":", 1)
        return brand, number
    return "", value


def _action_for(kind: str, bank: str, value: str) -> str:
    if kind == "ewallet":
        brand, _ = _wallet_parts(value)
        brand = _WALLET_BRAND.get(brand.lower(), brand) or bank or "ví điện tử"
        return f"Gửi {brand} đề nghị rà soát và tạm khóa ví nhận tiền."
    if kind == "crypto":
        return "Gửi sàn hoặc đơn vị phát hành stablecoin đề nghị đánh dấu địa chỉ ví."
    if bank:
        return f"Gửi {bank} đề nghị rà soát, tạm phong tỏa tài khoản nhận tiền."
    return "Gửi ngân hàng chủ quản đề nghị rà soát, tạm phong tỏa tài khoản nhận tiền."


def _destinations(state: AgentState) -> list[dict]:
    rows = []
    seen = set()
    for check in state.account_checks or []:
        kind = _BUCKET_KIND.get(check.get("kind", ""), check.get("kind") or "bank")
        key = (kind, re.sub(r"\W", "", str(check.get("value", ""))).lower())
        seen.add(key)
        rows.append(
            {
                "kind": kind,
                "kind_label": _KIND_LABEL.get(kind, "Nơi nhận tiền"),
                "value": check.get("value", ""),
                "bank": check.get("bank", ""),
                "holder": check.get("holder", ""),
                "confirmed": bool(check.get("confirmed")),
                "confirmed_how": check.get("how", "") if check.get("confirmed") else "",
                "first_turn": check.get("first_turn", 0),
            }
        )
    ind = state.indicators or {}
    for kind, bucket in (("bank", "bank_accounts"), ("ewallet", "ewallets"), ("crypto", "crypto_wallets")):
        for value in ind.get(bucket) or []:
            key = (kind, re.sub(r"\W", "", str(value)).lower())
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "kind": kind,
                    "kind_label": _KIND_LABEL[kind],
                    "value": value,
                    "bank": "",
                    "holder": "",
                    "confirmed": False,
                    "confirmed_how": "",
                    "first_turn": 0,
                }
            )
    for row in rows:
        row["raw"] = row["value"]
        row["value"], row["bank"] = _present(row["kind"], row["raw"], row["bank"])
        row["action"] = _action_for(row["kind"], row["bank"], row["raw"])
    rows.sort(key=lambda row: (not row["confirmed"], row["first_turn"]))
    return rows


def _contacts(state: AgentState) -> dict:
    ind = state.indicators or {}
    hotlines = set(ind.get("hotlines") or [])
    lookalikes = {str(item).split(" ", 1)[0].lower(): item for item in ind.get("lookalikes") or []}
    urls = []
    for url in ind.get("urls") or []:
        host = re.sub(r"^[a-z]+://", "", str(url).lower()).split("/", 1)[0]
        urls.append({"value": url, "note": str(lookalikes.get(host, ""))})
    return {
        "phones": [p for p in ind.get("phones") or [] if p not in hotlines],
        "urls": urls,
        "apk": list(ind.get("apk") or []),
        "zalo": list(ind.get("zalo") or []),
        "telegram": list(ind.get("telegram") or []),
        "remote_ids": list(ind.get("remote_ids") or []),
        "apps": list(ind.get("apps") or []),
    }


def _claims(state: AgentState) -> dict:
    who = ""
    for item in state.checklist or []:
        if item.get("key") == "who" and item.get("done"):
            who = item.get("detail") or ""
    ind = state.indicators or {}
    return {
        "posed_as": who,
        "brands": list(ind.get("brands") or []),
        "pressure": list(ind.get("pressure") or []),
        "techniques": list(ind.get("techniques") or []),
        "red_flags": [f.get("label", "") for f in state.risk_factors or [] if f.get("label")][:8],
    }


def _classification(session, conversation: Conversation, state: AgentState) -> dict:
    out = {
        "unmatched": bool(state.unmatched),
        "live_match": None,
        "extracted": None,
    }
    if state.match_history:
        last = state.match_history[-1]
        out["live_match"] = {"script_id": last.script_id, "title": last.title, "confidence": round(float(last.confidence or 0), 2)}
    if conversation.extracted_script_id:
        script = session.get(Script, conversation.extracted_script_id)
        if script is not None:
            target = session.get(Script, script.merge_target) if script.merge_target else None
            parent = session.get(Script, script.parent_id) if script.parent_id else None
            out["extracted"] = {
                "script_id": script.id,
                "title": script.title,
                "category": CATEGORIES.get(script.category, script.category),
                "relation": script.relation,
                "status": script.status,
                "summary": script.summary,
                "merge_target": {"id": target.id, "title": target.title} if target else None,
                "parent": {"id": parent.id, "title": parent.title} if parent else None,
            }
    return out


def _timeline(conversation: Conversation, state: AgentState, persona_name: str) -> list[dict]:
    stages = {}
    for entry in state.timeline or []:
        stages[entry.get("turn")] = entry
    rows = []
    turn = 0
    for message in conversation.messages:
        if message.role == "scammer":
            turn += 1
        entry = stages.get(turn) if message.role == "victim" else None
        rows.append(
            {
                "at": _iso(message.created_at),
                "who": "Đối tượng" if message.role == "scammer" else f"Nạn nhân mồi ({persona_name})",
                "role": message.role,
                "text": message.content,
                "stage": (entry or {}).get("stage_label", ""),
                "new_iocs": (entry or {}).get("new_iocs", []),
            }
        )
    return rows


def _digest(conversation: Conversation) -> str:
    body = "\n".join(f"{_iso(m.created_at)}|{m.role}|{m.content}" for m in conversation.messages)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_dossier(session, conversation: Conversation) -> dict:
    from app.services.intel import lookup

    state = AgentState.model_validate(conversation.state)
    persona = conversation.persona
    persona_name = persona.display_name if persona else state.persona_slug
    messages = conversation.messages
    try:
        links = lookup(session, state.indicators or {}, exclude=f"conv:{conversation.id}")
    except Exception:  # noqa: BLE001 - a missing graph should not block the export
        links = []
    destinations = _destinations(state)
    linked = {}
    for hit in links:
        linked[normalize_indicator(hit["kind"], str(hit["value"]))] = hit
    for row in destinations:
        bucket = {"bank": "bank_accounts", "ewallet": "ewallets", "crypto": "crypto_wallets"}[row["kind"]]
        hit = linked.get(normalize_indicator(bucket, str(row["raw"])))
        if hit is None and row["kind"] == "bank":
            hit = linked.get(re.sub(r"\D", "", str(row["value"])))
        row["seen_elsewhere"] = hit["seen_in"] if hit else []
    first = messages[0].created_at if messages else conversation.created_at
    last = messages[-1].created_at if messages else conversation.updated_at
    return {
        "kind": "honeypot-dossier",
        "version": 1,
        "case_id": f"HP-{conversation.id[:8].upper()}",
        "conversation_id": conversation.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel": conversation.channel,
        "is_demo": bool(conversation.is_demo),
        "status": conversation.status,
        "started_at": _iso(first),
        "ended_at": _iso(last),
        "turns": sum(1 for m in messages if m.role == "scammer"),
        "decoy": {
            "persona": persona_name,
            "note": "Nạn nhân mồi do hệ thống đóng vai. Mọi thông tin cá nhân, mã OTP phía nạn nhân đều là giả.",
        },
        "classification": _classification(session, conversation, state),
        "claims": _claims(state),
        "destinations": destinations,
        "contacts": _contacts(state),
        "cross_links": links,
        "timeline": _timeline(conversation, state, persona_name),
        "integrity": {
            "algorithm": "sha256",
            "transcript_digest": _digest(conversation),
            "note": "Băm toàn bộ lời thoại theo thứ tự (thời điểm|vai|nội dung). Tính lại để chứng minh bản ghi chưa bị sửa.",
        },
        "report_channels": REPORT_CHANNELS,
        "caveat": (
            "Số tài khoản và ví do đối tượng tự cung cấp cho nạn nhân mồi. Chủ tài khoản có thể là người cho thuê hoặc bị "
            "mượn tài khoản. Cần xác minh trước khi phong tỏa."
        ),
    }


def collect_destinations(session) -> list[dict]:
    """Every receiving account or wallet across conversations, merged by value."""
    merged: dict[tuple[str, str], dict] = {}
    rows = session.scalars(select(Conversation).order_by(Conversation.created_at)).all()
    for conv in rows:
        state = AgentState.model_validate(conv.state)
        family = ""
        if state.match_history and not state.unmatched:
            family = state.match_history[-1].title
        story = ""
        if conv.extracted_script_id:
            script = session.get(Script, conv.extracted_script_id)
            if script is not None:
                story = script.title
        for row in _destinations(state):
            norm = re.sub(r"\W", "", str(row["value"])).lower()
            key = (row["kind"], norm)
            item = merged.get(key)
            if item is None:
                item = merged[key] = {
                    "kind": row["kind"],
                    "kind_label": row["kind_label"],
                    "value": row["value"],
                    "bank": row["bank"],
                    "holders": [],
                    "confirmed": False,
                    "conversations": [],
                    "stories": [],
                    "first_seen": _iso(conv.created_at),
                    "last_seen": _iso(conv.created_at),
                    "action": row["action"],
                }
            item["bank"] = item["bank"] or row["bank"]
            if row["holder"] and row["holder"] not in item["holders"]:
                item["holders"].append(row["holder"])
            item["confirmed"] = item["confirmed"] or row["confirmed"]
            if conv.id not in item["conversations"]:
                item["conversations"].append(conv.id)
            label = story or family
            if label and label not in item["stories"]:
                item["stories"].append(label)
            item["last_seen"] = _iso(conv.created_at)
            item["action"] = _action_for(item["kind"], item["bank"], row["raw"])
    out = list(merged.values())
    for item in out:
        item["count"] = len(item["conversations"])
    out.sort(key=lambda item: (-len(item["stories"]), -item["count"], not item["confirmed"], item["value"]))
    return out


def destinations_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["loai", "so_tai_khoan_hoac_vi", "ngan_hang_vi", "chu_tai_khoan", "da_xac_nhan", "so_cuoc_thoai", "kich_ban", "lan_dau", "lan_cuoi", "de_nghi"])
    for row in rows:
        writer.writerow(
            [
                row["kind_label"],
                row["value"],
                row["bank"],
                "; ".join(row["holders"]),
                "có" if row["confirmed"] else "chưa",
                row["count"],
                " | ".join(row["stories"]),
                row["first_seen"][:10],
                row["last_seen"][:10],
                row["action"],
            ]
        )
    # Excel opens UTF-8 CSV correctly only with a BOM.
    return "﻿" + buf.getvalue()
