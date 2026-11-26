"""Aggregates over the published library. Dates come from the scripts themselves."""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Script
from app.taxonomy import CATEGORIES


def build_trends(session) -> dict:
    rows = list(session.scalars(select(Script).where(Script.status == "published")).all())
    now = datetime.now(timezone.utc)
    by_category = Counter(script.category for script in rows)
    by_brand = Counter(script.brand for script in rows if script.brand)
    by_channel = Counter(script.channel for script in rows)
    months: Counter[str] = Counter()
    for script in rows:
        seen = script.first_seen
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        months[seen.strftime("%Y-%m")] += 1
    month_keys = sorted(months)[-12:]
    newest = sorted(rows, key=lambda script: script.first_seen, reverse=True)[:6]
    rising = [
        script
        for script in rows
        if (now - (script.last_seen if script.last_seen.tzinfo else script.last_seen.replace(tzinfo=timezone.utc))).days <= 45
    ]
    rising.sort(key=lambda script: (script.occurrence_count, script.last_seen), reverse=True)

    def brief(script: Script) -> dict:
        return {
            "id": script.id,
            "title": script.title,
            "category": script.category,
            "category_label": CATEGORIES.get(script.category, script.category),
            "brand": script.brand,
            "occurrence_count": script.occurrence_count,
            "first_seen": script.first_seen.date().isoformat(),
            "last_seen": script.last_seen.date().isoformat(),
            "parent_id": script.parent_id,
        }

    def _aware(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    fresh: Counter[str] = Counter()
    for script in rows:
        if (now - _aware(script.first_seen)).days <= 240:
            fresh[script.category] += 1
    from app.models import Conversation

    branch_new: Counter[str] = Counter()
    families = {script.id: script for script in rows}
    for conv in session.scalars(select(Conversation)).all():
        created = conv.created_at
        if created is not None and (now - _aware(created)).days > 30:
            continue
        state = conv.state or {}
        for event in state.get("branch_events") or []:
            if event.get("kind") == "new":
                fam = families.get(event.get("family_id") or event.get("script_id") or "")
                branch_new[fam.category if fam else "other"] += 1
    emerging = []
    for category, count in by_category.items():
        share = fresh[category] / count if count else 0
        score = round(share * 60 + min(branch_new[category], 5) * 8, 1)
        if fresh[category] or branch_new[category]:
            emerging.append({
                "id": category,
                "label": CATEGORIES.get(category, category),
                "new_scripts": fresh[category],
                "total": count,
                "new_branches_30d": branch_new[category],
                "score": score,
            })
    emerging.sort(key=lambda item: item["score"], reverse=True)
    from app.data.warnings import STATS, WARNINGS

    watch = []
    for card in WARNINGS:
        covered = [script for script in rows if script.category in card["categories"]]
        latest = max((_aware(script.last_seen) for script in covered), default=None)
        watch.append({
            "id": card["id"],
            "title": card["title"],
            "rising": card["rising"],
            "first_reported": card["first_reported"],
            "scripts": len(covered),
            "latest": latest.date().isoformat() if latest else None,
            "source": card["sources"][0] if card["sources"] else None,
        })
    return {
        "emerging": emerging[:8],
        "watch": watch,
        "stats": STATS,
        "total": len(rows),
        "variants": sum(1 for script in rows if script.parent_id),
        "categories": [
            {"id": key, "label": CATEGORIES.get(key, key), "count": count}
            for key, count in by_category.most_common()
        ],
        "brands": [{"name": name, "count": count} for name, count in by_brand.most_common(8)],
        "channels": [{"id": key, "count": count} for key, count in by_channel.most_common()],
        "by_month": [{"month": key, "count": months[key]} for key in month_keys],
        "newest": [brief(script) for script in newest],
        "rising": [brief(script) for script in rising[:6]],
    }
