"""Which queue slots are due right now — stdlib only, so the publish workflow can ask
before installing Playwright.

GitHub's scheduled runs land hours late (Sep 2026: the 08:00 cron ran at ~13:30 BST and
the 20:00 cron after midnight), so the slot is never guessed from the clock. Every run
publishes whatever is due today and not yet out; the hourly cron is only a heartbeat.

    python -m engine.due        # prints "YYYY-MM-DD slot" lines + "comments" if any are due
    python -m engine.due --repair   # prints planned slots (today + tomorrow) with no usable post yet
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "queue"
BST = timezone(timedelta(hours=6))
DEFAULT_SLOTS = {"morning": "08:00", "evening": "20:00"}
LAST_HOUR = 23          # nothing goes out from 23:00 to the next slot — a midnight post reaches nobody
DONE = {"published", "skipped", "missed"}


def slot_times() -> dict[str, str]:
    try:
        return json.loads((ROOT / "project" / "project.json").read_text(encoding="utf-8")).get("slots") or DEFAULT_SLOTS
    except (OSError, ValueError):
        return DEFAULT_SLOTS


def _status(path: Path) -> str:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status", "")
    except (OSError, ValueError):
        return ""


def due_slots(now: datetime, queue_dir: Path = QUEUE_DIR, slots: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Slots of *today* (BST) whose time has passed, that have a queue file and are not published/skipped.
    Only slots with a queue file count: a day the planner left empty must not pull an evergreen post."""
    now = now.astimezone(BST)
    if now.hour >= LAST_HOUR:
        return []
    date = now.strftime("%Y-%m-%d")
    out = []
    for slot, hhmm in sorted((slots or slot_times()).items(), key=lambda kv: kv[1]):
        h, m = (int(x) for x in hhmm.split(":"))
        if now < now.replace(hour=h, minute=m, second=0, microsecond=0):
            continue
        path = queue_dir / date / f"{slot}.json"
        if path.exists() and _status(path) not in DONE:
            out.append((date, slot))
    return out


def comments_due(now: datetime, queue_dir: Path = QUEUE_DIR) -> bool:
    now_utc = now.astimezone(timezone.utc)
    for f in queue_dir.glob("*/*.json"):
        try:
            item = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if item.get("status") != "published" or not item.get("first_comment") or not item.get("published_at"):
            continue
        due = datetime.fromisoformat(item["published_at"]) + timedelta(minutes=item.get("comment_delay_minutes") or 0)
        if now_utc >= due:
            return True
    return False


WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _planned_slots(date: str) -> list[str]:
    """Slots strategy.json plans for a date (stdlib mirror of engine.planner, enough to spot gaps)."""
    try:
        strategy = json.loads((ROOT / "strategy.json").read_text(encoding="utf-8"))
        holidays = json.loads((ROOT / "data" / "holidays.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if date in holidays.get("skip_dates", {}):
        return []
    if date in holidays.get("single_evening_post_dates", {}):
        return ["evening"]
    weekday = WEEKDAYS[datetime.strptime(date, "%Y-%m-%d").weekday()]
    entries = strategy.get("date_overrides", {}).get(date) or strategy.get("calendar", {}).get(weekday, [])
    return [e.get("slot", "morning") for e in entries if isinstance(e, dict)]


def missing_slots(now: datetime, queue_dir: Path = QUEUE_DIR, slots: dict[str, str] | None = None,
                  grace_hours: int = 3) -> list[tuple[str, str]]:
    """Planned slots (today + tomorrow) with no queue file or a failed one. Today's slots more than
    `grace_hours` past are ignored: they can no longer go out on time."""
    now = now.astimezone(BST)
    times = slots or slot_times()
    out = []
    for offset in (0, 1):
        day = now + timedelta(days=offset)
        date = day.strftime("%Y-%m-%d")
        for slot in _planned_slots(date):
            h, m = (int(x) for x in times.get(slot, "08:00").split(":"))
            if day.replace(hour=h, minute=m, second=0, microsecond=0) < now - timedelta(hours=grace_hours):
                continue
            path = queue_dir / date / f"{slot}.json"
            if not path.exists() or _status(path) == "failed":
                out.append((date, slot))
    return out


def main() -> int:
    now = datetime.now(tz=BST)
    if "--repair" in sys.argv[1:]:
        for date, slot in missing_slots(now):
            print(date, slot)
        return 0
    for date, slot in due_slots(now):
        print(date, slot)
    if comments_due(now):
        print("comments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
