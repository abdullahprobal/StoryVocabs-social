"""Apply the owner's Telegram decisions to the queue and answer them.

    python -m engine.review            # read new messages, update queue items, reply in Telegram
                                       # exit code 3 = at least one item needs regeneration (a note)

Runs every 30 minutes from review.yml and at the start of every publish run, so
an "approve" typed at 07:03 gets a reply within minutes, not at post time.

Rules
  * a decision that is a reply to a card applies to that card
  * a plain message (no reply) applies to the newest card still waiting
  * approve → status=approved, reply with the post day/time
  * skip    → status=skipped, reply; the slot falls back to evergreen
  * note    → review_note stored, reply; the caller regenerates (needs Playwright)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from engine import settings
from engine.contracts import QueueItem
from engine.generate import load_item, save_item
from engine.publishers import telegram
from engine.publishers.telegram import PILLAR_LABELS


def log(msg: str) -> None:
    print(msg, flush=True)


def waiting_items() -> list[tuple[Path, QueueItem]]:
    """Queue items that have a preview card and no final decision yet, newest card first."""
    out = []
    for f in sorted(settings.QUEUE_DIR.glob("*/*.json")):
        it = load_item(f)
        if it and it.telegram_message_id and it.status in ("pending", "approved", "failed"):
            out.append((f, it))
    out.sort(key=lambda p: p[1].telegram_message_id or 0, reverse=True)
    return out


def _when(item: QueueItem) -> str:
    try:
        day = datetime.strptime(item.date, "%Y-%m-%d").strftime("%A %d %b")
    except ValueError:
        day = item.date
    return f"{day}, {'8:00 AM' if item.slot == 'morning' else '8:00 PM'} BST"


def _label(item: QueueItem) -> str:
    return f"{PILLAR_LABELS.get(item.pillar, item.pillar)} · {_when(item)}"


def apply_decisions(decisions: list[dict] | None = None) -> list[tuple[Path, QueueItem]]:
    """Apply decisions; return the items that need regeneration."""
    decisions = telegram.read_decisions() if decisions is None else decisions
    if not decisions:
        log("no new decisions")
        return []
    waiting = waiting_items()
    by_card = {it.telegram_message_id: (f, it) for f, it in waiting}
    pending_only = [(f, it) for f, it in waiting if it.status == "pending"]
    to_regen: list[tuple[Path, QueueItem]] = []

    for d in decisions:
        target = by_card.get(d["reply_to"]) if d["reply_to"] else (pending_only[0] if pending_only else None)
        if target is None and d["reply_to"] is None and waiting:
            target = waiting[0]  # nothing pending: act on the newest card anyway (e.g. re-approve)
        if target is None:
            telegram.reply("Nothing is waiting for review right now. The next card arrives with the morning generation.",
                           d["message_id"])
            log(f"decision {d['kind']} with no target")
            continue
        path, it = target
        if d["kind"] == "approve":
            if it.status == "published":
                telegram.reply(f"Already posted: {_label(it)}.", d["message_id"])
                continue
            it.status = "approved"
            it.review_note = ""
            save_item(it, path)
            telegram.reply(f"✅ Approved — {_label(it)}.\nIt will post automatically at that time; "
                           f"I'll send you the Facebook link as soon as it's live.", d["message_id"])
            log(f"approved {it.id}")
        elif d["kind"] == "skip":
            it.status = "skipped"
            it.review_note = d["text"]
            save_item(it, path)
            telegram.reply(f"❌ Skipped — {_label(it)}.\nA ready-made backup post will take that slot instead.", d["message_id"])
            log(f"skipped {it.id}")
        elif d["kind"] == "note":
            if not d["text"]:
                telegram.reply("Tell me what to change, e.g. “edit: make the hook a question”.", d["message_id"])
                continue
            it.status = "pending"
            it.review_note = d["text"]
            save_item(it, path)
            to_regen.append((path, it))
            telegram.reply(f"✏️ Got it — regenerating {_label(it)} with your note. A new card is coming; "
                           f"reply to that one.", d["message_id"])
            log(f"note for {it.id}: {d['text'][:60]}")
        if (path, it) in pending_only:
            pending_only.remove((path, it))
    return to_regen


def regenerate(items: list[tuple[Path, QueueItem]]) -> None:
    from engine.publish import regenerate_with_note
    from engine.generate import after_build
    for path, it in items:
        new = regenerate_with_note(it, it.review_note)
        if new.status == "failed":
            telegram.reply(f"⚠ Couldn't produce a better version for {_label(it)}: {new.error[:120]}. "
                           f"The previous card still stands — approve it or skip it.")
            continue
        after_build(new, dry_run=False)
        save_item(new, path)
        log(f"regenerated {new.id}")


def main(argv=None) -> int:
    to_regen = apply_decisions()
    if to_regen and "--no-regenerate" in (argv or sys.argv[1:]):
        return 3
    if to_regen:
        regenerate(to_regen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
