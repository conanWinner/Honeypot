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

    return {
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
