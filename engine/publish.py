"""Publish the queue item for a slot (or the pending comment jobs).

    python -m engine.publish --slot morning            # today's morning slot (BST)
    python -m engine.publish --date 2026-09-20 --slot morning
    python -m engine.publish --comments                # post due first-comments (quiz answers)
    python -m engine.publish --dry-run

Flow
  1. load queue/<date>/<slot>.json; if missing or failed → evergreen fallback
  2. read Telegram decisions: skip / note (regenerate once) / approve
  3. REVIEW_MODE: review → publish unless skipped; manual → publish only if approved; autopilot → publish
  4. ensure media_urls (upload if needed) → FB carousel → IG carousel → stories → first comment (or schedule)
  5. save ids, notify Telegram
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import settings
from engine.contracts import QueueItem
from engine.generate import build_item, load_item, queue_path, rerender, save_item
from engine.planner import PlanItem, load_strategy
from engine.publishers import media_host, meta, telegram


def log(msg: str) -> None:
    print(msg, flush=True)


def pick_evergreen(date_str: str, slot: str) -> QueueItem | None:
    files = sorted(settings.EVERGREEN_DIR.glob("*.json"))
    for f in files:
        item = load_item(f)
        if item and item.status == "pending":
            item.date, item.slot, item.evergreen = date_str, slot, True
            f.rename(f.with_suffix(".used"))
            return item
    return None


def ensure_urls(item: QueueItem) -> None:
    if item.media_urls and (item.story_media_url or not item.story_media):
        return
    if not media_host.configured():
        raise RuntimeError("media host not configured and item has no media_urls")
    present = [p for p in item.media if Path(p).exists()]
    if not item.media or len(present) != len(item.media) or (item.story_media and not Path(item.story_media).exists()):
        log("    slides not on disk — re-rendering from stored content")
        rerender(item)
    item.media_urls = media_host.upload_many(item.media, f"{item.date}/{item.slot}")
    if item.story_media and Path(item.story_media).exists():
        item.story_media_url = media_host.upload_many([item.story_media], f"{item.date}/{item.slot}")[0]


def regenerate_with_note(item: QueueItem, note: str) -> QueueItem:
    strategy = load_strategy()
    strategy = dict(strategy)
    hooks = dict(strategy["hook_styles"])
    hooks[item.hook_style] = {"instruction": f"{hooks.get(item.hook_style, {}).get('instruction', '')}\nOWNER NOTE: {note}"}
    strategy["hook_styles"] = hooks
    plan = PlanItem(date=item.date, slot=item.slot, pillar=item.pillar, time_bst="", hook_style=item.hook_style)
    new = build_item(plan, strategy, dry_run=settings.DRY_RUN)
    new.review_note = note
    return new


def publish_item(item: QueueItem) -> QueueItem:
    ensure_urls(item)
    if not meta.configured():
        raise RuntimeError("META_PAGE_ID / META_PAGE_TOKEN not set")
    if not item.fb_post_id:
        item.fb_post_id = meta.fb_publish(item.media_urls, item.caption_fb)
        log(f"    facebook post {item.fb_post_id}")
    if settings.PUBLISH_TO_INSTAGRAM and settings.META_IG_USER_ID and not item.ig_media_id:
        try:
            item.ig_media_id = meta.ig_publish(item.media_urls, item.caption_ig)
            log(f"    instagram media {item.ig_media_id}")
        except meta.MetaError as e:
            log(f"    ⚠ instagram failed: {e}")
            item.error = f"ig: {e}"
    if settings.PUBLISH_STORIES and item.story_media_url:
        try:
            if not item.fb_story_id:
                item.fb_story_id = meta.fb_story(item.story_media_url)
            if settings.META_IG_USER_ID and item.ig_media_id and not item.ig_story_id:
                item.ig_story_id = meta.ig_story(item.story_media_url)
        except meta.MetaError as e:
            log(f"    ⚠ story failed: {e}")
    if item.first_comment and item.comment_delay_minutes == 0:
        post_first_comment(item)
    item.status = "published"
    item.published_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return item


def post_first_comment(item: QueueItem) -> None:
    try:
        if item.fb_post_id:
            meta.fb_comment(item.fb_post_id, item.first_comment)
        if item.ig_media_id:
            meta.ig_comment(item.ig_media_id, item.first_comment)
        item.first_comment = ""  # mark done
        log("    first comment posted")
    except meta.MetaError as e:
        log(f"    ⚠ comment failed: {e}")


def run_slot(date_str: str, slot: str) -> int:
    path = queue_path(date_str, slot)
    item = load_item(path)
    if item and item.status == "published":
        log(f"{date_str} {slot}: already published ({item.fb_post_id})")
        return 0
    if item and item.status == "skipped":
        log(f"{date_str} {slot}: skipped by owner")
        return 0

    # Apply anything the owner said since the last check (same logic as the 30-minute review job).
    if telegram.configured():
        from engine.review import apply_decisions, regenerate
        to_regen = apply_decisions()
        if to_regen:
            regenerate(to_regen)
        item = load_item(path)
    if item and item.status == "skipped":
        log(f"{date_str} {slot}: skipped by owner")
        item = None

    if item is None or item.status == "failed":
        if item is not None:
            log(f"  queue item failed earlier: {item.error}")
        item = pick_evergreen(date_str, slot)
        if item is None:
            log(f"{date_str} {slot}: nothing to publish and no evergreen left")
            telegram.notify(f"⚠ {date_str} {slot}: nothing to publish (no queue item, evergreen empty).")
            return 1
        log(f"  using evergreen item {item.id} ({item.pillar})")
        save_item(item, path)

    if settings.REVIEW_MODE == "manual" and item.status != "approved":
        log(f"{date_str} {slot}: REVIEW_MODE=manual and not approved — waiting")
        from engine.review import _label
        telegram.notify(f"⏸ Not posted — {_label(item)} is still waiting for your ✅. "
                        f"Reply “approve” to the card and it goes out at the next run.")
        return 0

    try:
        item = publish_item(item)
        save_item(item, path)
        link = f"https://www.facebook.com/{item.fb_post_id}" if item.fb_post_id and not settings.DRY_RUN else "(dry-run)"
        telegram.notify(f"✅ Published {date_str} {slot} · {item.pillar}\n{link}"
                        + (f"\nIG: {item.ig_media_id}" if item.ig_media_id else ""))
        log(f"{date_str} {slot}: published")
        return 0
    except Exception as e:  # noqa: BLE001
        item.error = f"publish: {e}"
        save_item(item, path)
        log(f"  ✗ publish failed: {e}")
        telegram.notify(f"❌ Publish failed {date_str} {slot}: {e}")
        return 1


def run_comments() -> int:
    """Post first-comments whose delay has elapsed (quiz answers)."""
    now = datetime.now(timezone.utc)
    n = 0
    for f in sorted(settings.QUEUE_DIR.glob("*/*.json")):
        item = load_item(f)
        if not item or item.status != "published" or not item.first_comment or not item.published_at:
            continue
        due = datetime.fromisoformat(item.published_at) + timedelta(minutes=item.comment_delay_minutes)
        if now >= due:
            log(f"  comment due for {item.id}")
            post_first_comment(item)
            save_item(item, f)
            n += 1
    log(f"comments posted: {n}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--slot", choices=["morning", "evening"])
    ap.add_argument("--comments", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.dry_run:
        settings.DRY_RUN = True
    if a.comments:
        return run_comments()
    date_str = a.date or settings.today_bst()
    slot = a.slot
    if not slot:
        slot = "morning" if settings.now_bst().hour < 14 else "evening"
    return run_slot(date_str, slot)


if __name__ == "__main__":
    sys.exit(main())
