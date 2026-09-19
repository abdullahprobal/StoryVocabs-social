"""Launch backfill: fill the Page with a month of posts in a couple of days.

Facebook lets a Page post with `backdated_time`, so the posts appear spread over the past
weeks instead of landing as one burst; followers are not notified for back-dated posts.
Instagram cannot backdate, so only the first `--ig` items also go to the IG grid, published
in the order they were approved, a few per run.

    python -m engine.backfill --count 30 --days-back 30 --ig 12 [--dry-run]

Builds queue/backfill/NN_<pillar>.json (status pending) through the same writer, gates,
critic and renderer as the daily posts, then sends one numbered Telegram lineup. Nothing is
published until the owner replies "approve all" (or approves numbers); then
    python -m engine.publish --backfill --batch 10
posts the approved items, oldest date first.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import timedelta
from pathlib import Path

from engine import settings
from engine.contracts import QueueItem
from engine.generate import build_item, log, save_item
from engine.lineup import send_lineup
from engine.planner import PlanItem, load_strategy, pick_hook_style

BACKFILL_DIR = settings.QUEUE_DIR / "backfill"

# Pillar mix for a 30-post backfill (scaled for other counts). in_app only when screenshots exist.
MIX = [("news_word", 8), ("quiz", 7), ("confusables", 6), ("story60", 5), ("offer", 2), ("in_app", 2)]


def pillar_sequence(count: int, strategy: dict) -> list[str]:
    have_screens = bool(strategy.get("in_app_screens"))
    mix = [(p, n) for p, n in MIX if p != "in_app" or have_screens]
    if not have_screens:
        mix = [(p, n + 2) if p == "confusables" else (p, n) for p, n in mix]
    total = sum(n for _, n in mix)
    seq: list[str] = []
    for p, n in mix:
        seq += [p] * max(1, round(n * count / total))
    seq = seq[:count]
    while len(seq) < count:
        seq.append("confusables")
    # interleave so no two same pillars sit next to each other on the timeline
    rng = random.Random(count)
    for _ in range(50):
        rng.shuffle(seq)
        if all(a != b for a, b in zip(seq, seq[1:])):
            break
    # the newest post (last) should sell: put an offer at the end if we have one
    if "offer" in seq:
        seq.remove("offer"); seq.append("offer")
    return seq


def build(count: int, days_back: int, ig: int, dry_run: bool) -> list[tuple[Path, QueueItem]]:
    strategy = load_strategy()
    BACKFILL_DIR.mkdir(parents=True, exist_ok=True)
    today = settings.now_bst().date()
    seq = pillar_sequence(count, strategy)
    step = max(1, days_back // count)
    items: list[tuple[Path, QueueItem]] = []
    rng = random.Random(42)
    for n, pillar in enumerate(seq, 1):
        day = today - timedelta(days=(count - n + 1) * step)
        slot = "evening" if n % 3 == 0 else "morning"
        plan = PlanItem(date=day.isoformat(), slot=slot, pillar=pillar, time_bst=settings.SLOT_TIMES.get(slot, "08:00"),
                        hook_style=pick_hook_style(strategy, rng, pillar))
        log(f"backfill {n}/{count}: {plan.date} {slot} {pillar}")
        item = build_item(plan, strategy, dry_run=dry_run)
        item.backdated = True
        item.publish_ig = n > count - ig  # the newest `ig` posts also go to the Instagram grid
        path = BACKFILL_DIR / f"{n:02d}_{pillar}.json"
        if item.status == "failed":
            log(f"  ✗ {pillar} failed: {item.error[:100]} — slot dropped")
            continue
        save_item(item, path)
        items.append((path, item))
        log(f"  ✓ {item.id} score={item.quality_score} ig={item.publish_ig}")
    return items


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--days-back", type=int, default=30)
    ap.add_argument("--ig", type=int, default=12, help="how many of the newest items also go to Instagram")
    ap.add_argument("--dry-run", action="store_true", help="render only; no upload, no Telegram")
    ap.add_argument("--no-lineup", action="store_true")
    a = ap.parse_args(argv)
    items = build(a.count, a.days_back, a.ig, a.dry_run)
    log(f"backfill built {len(items)}/{a.count}")
    if items and not a.dry_run and not a.no_lineup:
        from engine.generate import after_build
        for path, it in items:
            after_build(it, dry_run=False, preview=False)
            save_item(it, path)
        send_lineup("backfill")
    return 0 if items else 1


if __name__ == "__main__":
    sys.exit(main())
