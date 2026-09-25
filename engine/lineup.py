"""The nightly lineup: every post for a date, numbered, in one Telegram batch.

    python -m engine.lineup --date 2026-09-20      # (re)send the lineup for a date

The owner looks once, answers once ("approve all", "skip 2", "edit 1: shorter hook") or says
nothing. In REVIEW_MODE=review silence means everything posts at its slot time.
state/lineup.json remembers which number maps to which queue item so replies can be resolved
even days later.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from engine import settings
from engine.contracts import QueueItem
from engine.generate import load_item, save_item
from engine.publishers import telegram
from engine.publishers.telegram import PILLAR_LABELS, _preview_text

STATE = settings.STATE_DIR / "lineup.json"
SLOT_ORDER = {"morning": 0, "evening": 1}


def _state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


_FAILED: list[QueueItem] = []  # failed items seen by the last items_for() call (shown in the lineup)


def items_for(date_str: str) -> list[tuple[Path, QueueItem]]:
    _FAILED.clear()
    out = []
    for f in sorted((settings.QUEUE_DIR / date_str).glob("*.json")):
        it = load_item(f)
        if it and it.status in ("pending", "approved"):
            out.append((f, it))
        elif it and it.status == "failed":
            _FAILED.append(it)
    out.sort(key=lambda p: SLOT_ORDER.get(p[1].slot, 9))
    return out


def _when(it: QueueItem) -> str:
    return {"morning": "8:00 AM", "evening": "8:00 PM"}.get(it.slot, it.slot)


def send_lineup(date_str: str) -> int:
    """Send numbered cards for every post on date_str plus one summary. Returns count."""
    items = items_for(date_str)
    if not items:
        telegram.notify(f"No posts are queued for {date_str}.")
        return 0
    backfill = date_str == "backfill"
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A %d %B")
    except ValueError:
        day = "Launch backfill" if backfill else date_str
    if backfill:
        telegram.notify(f"📦 Launch backfill — {len(items)} posts that will appear on the Page dated over the past weeks "
                        f"(the newest {sum(1 for _, i in items if i.publish_ig)} also go to Instagram).\n"
                        "Cards follow. They post ONLY after you reply — e.g. approve all · skip 4 9 · edit 12: your note")
    else:
        telegram.notify(f"🗓 Tomorrow's lineup — {day}\n{len(items)} post{'s' if len(items) != 1 else ''}. Cards follow; one reply at the end covers all of them.")
    mapping = {}
    for n, (path, it) in enumerate(items, 1):
        it.telegram_message_id = telegram.send_preview(it, number=n)
        save_item(it, path)
        mapping[str(n)] = {"id": it.id, "path": str(path.relative_to(settings.ROOT)).replace("\\", "/")}
    lines = [f"{n}. {(it.date + ' ') if backfill else ''}{_when(it)} · {PILLAR_LABELS.get(it.pillar, it.pillar)} — {it.caption_fb.splitlines()[0][:70]}"
             for n, (_, it) in enumerate(items, 1)]
    if backfill:
        rule = "Nothing posts until you reply. Reply once, e.g.  approve all   ·   approve 1-10   ·   skip 4, edit 7: shorter hook"
    elif settings.REVIEW_MODE == "review":
        rule = ("Nothing to do if you like them all — they post automatically.\n"
                "Otherwise reply once, e.g.  skip 2   ·   edit 1: shorter hook   ·   approve all")
    elif settings.REVIEW_MODE == "manual":
        rule = "Nothing posts until you reply. Reply once, e.g.  approve all   ·   approve 1, skip 2   ·   edit 2: shorter hook"
    else:
        rule = "Autopilot: these will post as shown."
    if _FAILED:
        lines += [f"✖ {_when(it)} · {PILLAR_LABELS.get(it.pillar, it.pillar)} — not made: {(it.error or 'unknown error')[:90]}"
                  f" (a backup post covers it if one is left)" for it in _FAILED]
    telegram.notify("📋 " + day + "\n" + "\n".join(lines) + "\n\n" + rule)
    st = _state()
    st[date_str] = mapping
    st["latest"] = date_str
    _save(st)
    return len(items)


def resolve_numbers(numbers, date_str: str | None = None) -> list[tuple[Path, QueueItem]]:
    """Map lineup numbers (or "all") to queue items using the latest (or given) lineup."""
    st = _state()
    date_str = date_str or st.get("latest")
    mapping = st.get(date_str or "", {})
    if not mapping:
        return []
    keys = list(mapping) if numbers == "all" else [str(n) for n in numbers]
    if numbers != "all" and not any(k in mapping for k in keys) and "backfill" in st and date_str != "backfill":
        mapping = st["backfill"]  # numbers above the daily lineup's range refer to the backfill lineup
    out = []
    for k in keys:
        entry = mapping.get(k)
        if not entry:
            continue
        path = settings.ROOT / entry["path"]
        it = load_item(path)
        if it:
            out.append((path, it))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="default: tomorrow (BST)")
    a = ap.parse_args(argv)
    date_str = a.date or (datetime.now(settings.BST) + timedelta(days=1)).strftime("%Y-%m-%d")
    n = send_lineup(date_str)
    print(f"lineup sent for {date_str}: {n} posts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
