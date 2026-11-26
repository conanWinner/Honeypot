"""Cross-conversation indicator graph.

Every account, domain, APK, wallet, Telegram/Zalo link and phone the agent harvested is a
node. Conversations and library scripts that mention it are linked to it. Connected
components with more than one source are the interesting part: the same mule account
behind two different stories, or one APK host reused by a new family.
"""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import select

from app.agent.casefile import normalize_indicator
from app.models import Conversation, Script
from app.taxonomy import CATEGORIES

KINDS = {
    "bank_accounts": "Tài khoản",
    "crypto_wallets": "Ví crypto",
    "apk": "File APK",
    "urls": "Tên miền",
    "telegram": "Telegram",
    "zalo": "Zalo",
    "remote_ids": "ID điều khiển",
    "phones": "Số điện thoại",
}


def _key(kind: str, value: str) -> str:
    value = normalize_indicator(kind, value)
    if kind == "urls":
        value = re.sub(r"^[a-z]+://", "", value).split("/", 1)[0].removeprefix("www.")
    return f"{kind}:{value}" if value else ""


def _iocs(indicators: dict | None) -> list[tuple[str, str, str]]:
    out = []
    hotlines = set((indicators or {}).get("hotlines") or [])
    for kind in KINDS:
        for value in (indicators or {}).get(kind) or []:
            if kind == "phones" and value in hotlines:
                continue
            key = _key(kind, str(value))
            if key:
                out.append((key, kind, key.split(":", 1)[1]))
    return out


def _sources(session) -> list[dict]:
    rows = []
    for script in session.scalars(select(Script).where(Script.status.in_(("published", "pending")))).all():
        if script.indicators:
            rows.append(
                {
                    "id": f"script:{script.id}",
                    "type": "script",
                    "label": script.title,
                    "category": script.category,
                    "ref": script.id,
                    "indicators": script.indicators,
                }
            )
    for conv in session.scalars(select(Conversation)).all():
        state = conv.state or {}
        ind = state.get("indicators") or {}
        if not ind:
            continue
        family = ""
        history = state.get("match_history") or []
        if history:
            family = history[-1].get("family_id") or history[-1].get("script_id") or ""
        rows.append(
            {
                "id": f"conv:{conv.id}",
                "type": "conversation",
                "label": f"Hội thoại {conv.id[:8]}",
                "category": "",
                "ref": conv.id,
                "family": family,
                "indicators": ind,
                "created_at": conv.created_at.isoformat() if conv.created_at else "",
            }
        )
    return rows


def build_graph(session, min_sources: int = 1, limit: int = 300) -> dict:
    sources = _sources(session)
    families = {s.id: s for s in session.scalars(select(Script)).all()}
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_by: dict[str, set[str]] = defaultdict(set)
    for src in sources:
        if src["type"] == "conversation" and src.get("family") in families:
            fam = families[src["family"]]
            src["category"] = fam.category
            src["label"] = f"{src['label']} · {fam.title[:40]}"
        nodes[src["id"]] = {k: src[k] for k in ("id", "type", "label", "category", "ref")}
        for key, kind, value in _iocs(src["indicators"]):
            seen_by[key].add(src["id"])
            if key not in nodes:
                nodes[key] = {"id": key, "type": "ioc", "kind": kind, "kind_label": KINDS[kind], "label": value}
            edges.append({"source": src["id"], "target": key})
    for key, owners in seen_by.items():
        nodes[key]["sources"] = len(owners)
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adj[edge["source"]].add(edge["target"])
        adj[edge["target"]].add(edge["source"])
    comp_of: dict[str, int] = {}
    clusters = []
    for start in adj:
        if start in comp_of:
            continue
        stack, members = [start], []
        comp_of[start] = len(clusters)
        while stack:
            cur = stack.pop()
            members.append(cur)
            for nxt in adj[cur]:
                if nxt not in comp_of:
                    comp_of[nxt] = len(clusters)
                    stack.append(nxt)
        srcs = [nodes[m] for m in members if nodes[m]["type"] != "ioc"]
        iocs = [nodes[m] for m in members if nodes[m]["type"] == "ioc"]
        shared = [n for n in iocs if n.get("sources", 0) >= 2]
        cats = sorted({CATEGORIES.get(s["category"], s["category"]) for s in srcs if s.get("category")})
        clusters.append(
            {
                "id": len(clusters),
                "sources": srcs,
                "iocs": sorted(iocs, key=lambda n: -n.get("sources", 0)),
                "shared": shared,
                "categories": cats,
                "cross_family": len(cats) > 1,
            }
        )
    clusters = [c for c in clusters if len(c["sources"]) >= max(1, min_sources)]
    clusters.sort(key=lambda c: (len(c["shared"]), len(c["sources"])), reverse=True)
    linked = [c for c in clusters if c["shared"]]
    return {
        "nodes": list(nodes.values())[:limit],
        "edges": edges[: limit * 2],
        "clusters": clusters[:40],
        "stats": {
            "sources": len(sources),
            "iocs": sum(1 for n in nodes.values() if n["type"] == "ioc"),
            "shared_iocs": sum(1 for n in nodes.values() if n["type"] == "ioc" and n.get("sources", 0) >= 2),
            "linked_clusters": len(linked),
            "cross_family_clusters": sum(1 for c in linked if c["cross_family"]),
        },
    }


def lookup(session, indicators: dict, exclude: str = "") -> list[dict]:
    """Where else each harvested indicator was seen. Used by /check and the live panel."""
    wanted = {key: (kind, value) for key, kind, value in _iocs(indicators)}
    if not wanted:
        return []
    hits: dict[str, list[dict]] = defaultdict(list)
    for src in _sources(session):
        if exclude and src["id"] == exclude:
            continue
        for key, _kind, _value in _iocs(src["indicators"]):
            if key in wanted:
                hits[key].append({"type": src["type"], "label": src["label"], "ref": src["ref"]})
    return [
        {
            "kind": wanted[key][0],
            "kind_label": KINDS[wanted[key][0]],
            "value": wanted[key][1],
            "seen_in": seen[:6],
            "count": len(seen),
        }
        for key, seen in hits.items()
    ]
