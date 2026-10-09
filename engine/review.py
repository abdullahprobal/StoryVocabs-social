"""Apply the owner's Telegram decisions to the queue and answer them.

    python -m engine.review            # read new messages, update queue items, reply in Telegram
                                       # exit code 3 = at least one item needs regeneration (a note)

Runs every 30 minutes from review.yml and at the start of every publish run, so
an "approve" typed at 21:15 gets a reply within minutes, not at post time.

How a message is resolved
  * reply to a specific card                → that card
  * numbers ("skip 2", "1 ok, 2 skip")      → those items of the latest lineup
  * "approve all" / "skip all"              → every item of the latest lineup
  * bare "approve" / "skip" (no number)     → every item still waiting in the latest lineup;
                                              if there is no lineup, the newest waiting card
  * "edit 2: note" / "edit: note"           → regenerate that item (or the single waiting one)
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


def _targets(d: dict, waiting: list[tuple[Path, QueueItem]]) -> list[tuple[str, list[tuple[Path, QueueItem]], str]]:
    """Turn one owner message into [(kind, [items], note)] using cards, numbers or the lineup."""
    from engine.lineup import resolve_numbers
    by_card = {it.telegram_message_id: (f, it) for f, it in waiting}
    if d.get("reply_to") and d["reply_to"] in by_card:
        b = d.get("batch") or [{"kind": d["kind"], "numbers": None, "note": d.get("payload", d.get("text", ""))}]
        note = (b[0].get("note") or d.get("payload", "")) if b[0]["kind"] == "note" else d["text"]
        return [(b[0]["kind"], [by_card[d["reply_to"]]], note)]
    out = []
    batch = d.get("batch") or [{"kind": d["kind"], "numbers": None, "note": d.get("payload", "")}]
    for b in batch:
        if b["numbers"] in ("all", None):
            items = resolve_numbers("all")
            if b["numbers"] is None:
                items = [(p, it) for p, it in items if it.status == "pending"] or items
            if not items:
                pend = [(p, it) for p, it in waiting if it.status == "pending"]
                items = [pend[0]] if pend else (waiting[:1] if waiting else [])
        else:
            items = resolve_numbers(b["numbers"])
        out.append((b["kind"], items, b.get("note", "")))
    return out


def add_voice_rule(note: str) -> None:
    """Append an owner's standing instruction to project/voice.md (the writer + critic system prompt).
    'never say X' / 'don't write X' also lands in '## Never write' so the register gate enforces it."""
    import re
    note = note.strip()
    if not note:
        return
    path = settings.VOICE_FILE
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if "## Owner notes" not in text:
        text = text.rstrip() + "\n\n## Owner notes\n"
    head, rest = text.split("## Owner notes", 1)
    block, sep, tail = rest.partition("\n## ")
    block = block.rstrip() + f"\n- {note}\n"
    text = head + "## Owner notes" + block + (sep + tail if sep else "")
    m = re.search(r"(?:never (?:say|write|use)|don'?t (?:say|write|use)|avoid)\s+[\"“']?([^\"”',;.\n]+)", note, re.I)
    if m and "## Never write" in text:
        word = m.group(1).strip()
        h, nw = text.split("## Never write", 1)
        block, sep, tail = nw.partition("\n## ")
        if f"- {word}" not in block:
            block = block.rstrip() + f"\n- {word}\n"
        text = h + "## Never write" + block + (sep + tail if sep else "")
    path.write_text(text, encoding="utf-8")
    log(f"voice rule added: {note[:80]}")


def apply_decisions(decisions: list[dict] | None = None) -> list[tuple[Path, QueueItem]]:
    """Apply decisions; return the items that need regeneration."""
    decisions = telegram.read_decisions() if decisions is None else decisions
    if not decisions:
        log("no new decisions")
        return []
    waiting = waiting_items()
    to_regen: list[tuple[Path, QueueItem]] = []

    for d in decisions:
        if d.get("kind") == "voice":
            note = d.get("note") or d.get("text") or ""
            add_voice_rule(note)
            telegram.reply("📝 Added to the voice rules — every post from now on follows it:\n" + note, d["message_id"])
            continue
        groups = _targets(d, waiting)
        if not groups or all(not items for _, items, _ in groups):
            telegram.reply("I couldn't match that to a post. Use the number from the lineup, e.g. “skip 2” or “approve all”.",
                           d["message_id"])
            log(f"unmatched: {d['text'][:60]}")
            continue
        replies = []
        for kind, items, note in groups:
            for path, it in items:
                it = load_item(path) or it
                if kind == "approve":
                    if it.status == "published":
                        replies.append(f"• already posted: {_label(it)}")
                        continue
                    it.status, it.review_note = "approved", ""
                    save_item(it, path)
                    replies.append(f"✅ {_label(it)}")
                    log(f"approved {it.id}")
                elif kind == "skip":
                    it.status, it.review_note = "skipped", d["text"]
                    save_item(it, path)
                    replies.append(f"❌ skipped {_label(it)} — nothing will publish in that slot")
                    log(f"skipped {it.id}")
                elif kind == "note":
                    if not note:
                        replies.append("✏️ tell me what to change, e.g. “edit 2: make the hook a question”")
                        continue
                    it.status, it.review_note = "pending", note
                    save_item(it, path)
                    to_regen.append((path, it))
                    replies.append(f"✏️ regenerating {_label(it)} with your note — new card coming")
                    log(f"note for {it.id}: {note[:60]}")
        if replies:
            tail = "" if any(r.startswith("✏️") for r in replies) else "\nApproved posts go out automatically at their time; I'll send the link when each is live."
            telegram.reply("\n".join(replies) + tail, d["message_id"])
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
