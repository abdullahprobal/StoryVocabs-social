"""Telegram review channel (stateless: works from cron via getUpdates).

send_preview(item)      → message_id of the caption message (slides sent as a media group first)
decisions(since_update) → {message_id: ("skip"|"note"|"approve", text)} from the owner's replies
notify(text)            → plain message

Owner replies to the preview message with:
    ❌  or  skip          → slot is skipped (evergreen fallback used)
    ✏️ <note> / edit: ... → regenerate once with the note, then publish
    ✅  or  ok            → explicit approval (needed only in REVIEW_MODE=manual)
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from engine import settings

API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
STATE = settings.STATE_DIR / "telegram.json"


def configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def _state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"offset": 0}


def _save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def notify(text: str) -> int | None:
    if not configured():
        return None
    r = requests.post(f"{API}/sendMessage", data={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text[:4000],
                                                  "disable_web_page_preview": True}, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


class _Labels(dict):
    """Built-in pillar labels plus project/pillars/*.json labels, resolved lazily."""

    def get(self, key, default=None):
        if key in self:
            return dict.get(self, key)
        try:
            from engine.writers.generic import spec_for
            spec = spec_for(key)
            if spec and spec.get("label"):
                return spec["label"]
        except Exception:  # noqa: BLE001
            pass
        return default if default is not None else key


PILLAR_LABELS = _Labels({"news_word": "News Word", "quiz": "Quiz", "confusables": "Confusables",
                         "in_app": "In the App", "story60": "Story in 60s", "offer": "Community / Offer"})


def _preview_text(item, number: int | None = None) -> str:
    """Review card: what a reader will see, then how to decide. No internal ids or scores.
    `number` is the item's position in the nightly lineup (so the owner can say "skip 2")."""
    from datetime import datetime
    try:
        day = datetime.strptime(item.date, "%Y-%m-%d").strftime("%a %d %b")
    except ValueError:
        day = item.date
    when = {"morning": "8:00 AM", "evening": "8:00 PM"}.get(item.slot, item.slot)
    slides = f"{len(item.media)} slide{'s' if len(item.media) != 1 else ''}"
    tag = f"#{number} · " if number else ""
    head = f"📋 {tag}{day} · {when} · {PILLAR_LABELS.get(item.pillar, item.pillar)} · {slides}\n\n"
    if settings.REVIEW_MODE == "manual":
        rule = "Nothing is posted until you approve."
    elif settings.REVIEW_MODE == "review":
        rule = f"Posts automatically at {when} unless you skip it."
    else:
        rule = "Autopilot is on; this is a copy of what will post."
    tail = "\n\n————————————\n" + rule
    if getattr(item, "writer_model", ""):
        wm = item.writer_model.split(":", 1)[-1]
        cm = (item.critic_model or "").split(":", 1)[-1]
        tail += f"\nwritten by {wm}" + (f" · checked by {cm}" if cm else "") + (f" · {item.quality_score:g}/10" if item.quality_score else "")
    if number:
        tail += f"\nIn one reply: approve all · skip {number} · edit {number}: your note"
    else:
        tail += "\nReply: approve · skip · edit: your note"
    return (head + item.caption_fb + tail)[:4000]


_NUM = r"(?:#?\d+(?:\s*[,&]?\s*(?:and\s+)?#?\d+)*)"


def parse_batch(text: str) -> list[dict]:
    """Parse one owner reply that may address several numbered lineup items.

    Returns [{"kind": approve|skip|note, "numbers": [int] | "all" | None, "note": str}].
    Examples:  "approve all" → approve all · "skip 2" → skip [2] · "1 ok, 2 skip" → approve [1], skip [2]
               "edit 3: shorter hook" → note [3] · "approve" (no numbers) → approve, numbers=None (caller decides)
    """
    import re
    t = (text or "").strip()
    if not t:
        return []
    out: list[dict] = []
    # "voice: never say কৃত্রিম" → a standing rule appended to project/voice.md (applies to every future post)
    m = re.match(r"^\s*(?:voice|rule|style)\s*[:\-–]\s*(.+)$", t, re.I | re.S)
    if m:
        return [{"kind": "voice", "numbers": None, "note": m.group(1).strip()}]
    # "edit N: note" / "✏️ N note" / "edit: note" (no number)
    m = re.match(r"^\s*(?:✏️?|edit|note|change|fix|redo|regenerate)\s*#?(\d+)?\s*[:\-–]?\s*(.*)$", t, re.I | re.S)
    if m and not re.match(r"^\s*(approve|ok|skip)", t, re.I):
        n = [int(m.group(1))] if m.group(1) else None
        return [{"kind": "note", "numbers": n, "note": m.group(2).strip()}]
    low = t.lower()
    # segment on commas / newlines / ";" so "1 ok, 2 skip" and "skip 2 and 3" both work
    for seg in re.split(r"[,\n;]+|(?<=\d)\s+(?=(?:approve|skip|ok|no|yes)\b\s*#?\d)|(?<=[a-z])\s+(?=#?\d+\s+(?:approve|skip|ok|no|yes)\b)", low):
        seg = seg.strip()
        if not seg:
            continue
        kind = None
        if re.search(r"\b(skip|no|reject|drop|cancel)\b|❌", seg):
            kind = "skip"
        elif re.search(r"\b(approve|approved|ok|okay|yes|go|post|publish|confirm|good|fine)\b|✅|👍", seg):
            kind = "approve"
        if not kind:
            continue
        nums = [int(x) for x in re.findall(r"#?(\d+)", seg)]
        if re.search(r"\b(all|everything|both)\b", seg):
            out.append({"kind": kind, "numbers": "all", "note": ""})
        else:
            out.append({"kind": kind, "numbers": nums or None, "note": ""})
    return out


def send_preview(item, number: int | None = None) -> int:
    """Send slides as an album, then the caption + instructions. Returns the caption message id."""
    media = []
    files = {}
    for i, p in enumerate(item.media[:10]):
        key = f"f{i}"
        files[key] = (Path(p).name, Path(p).read_bytes(), "image/png")
        media.append({"type": "photo", "media": f"attach://{key}"})
    if media:
        r = requests.post(f"{API}/sendMediaGroup", data={"chat_id": settings.TELEGRAM_CHAT_ID, "media": json.dumps(media)},
                          files=files, timeout=180)
        r.raise_for_status()
    r = requests.post(f"{API}/sendMessage", data={"chat_id": settings.TELEGRAM_CHAT_ID,
                                                  "text": _preview_text(item, number),
                                                  "disable_web_page_preview": True}, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


def edit_preview(item) -> int | None:
    """Refresh an existing preview without sending a duplicate message.

    Telegram returns a harmless 400 when the text is already identical; treat
    that response as success so this command is safe to run repeatedly.
    """
    if not configured() or not item.telegram_message_id:
        return None
    r = requests.post(f"{API}/editMessageText", data={
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "message_id": item.telegram_message_id,
        "text": _preview_text(item),
        "disable_web_page_preview": True,
    }, timeout=60)
    if not r.ok:
        try:
            detail = r.json().get("description", "")
        except ValueError:
            detail = ""
        if "message is not modified" not in detail.lower():
            r.raise_for_status()
    return item.telegram_message_id


def classify(text: str) -> tuple[str, str] | None:
    """Map an owner message to (kind, payload). Plain words work; no emoji needed."""
    t = (text or "").strip()
    low = t.lower().lstrip("✅❌✏️ ").strip()
    if not t:
        return None
    if low.startswith(("skip", "no", "reject", "cancel")) or t.startswith("❌") or low in ("x", "n"):
        return ("skip", t)
    if low.startswith(("edit", "note", "change", "fix", "redo", "regenerate")) or t.startswith("✏"):
        note = t.split(" ", 1)[1].strip() if " " in t else ""
        note = note.lstrip(":").strip()
        return ("note", note)
    if low.startswith(("ok", "okay", "yes", "approve", "approved", "go", "publish", "post", "confirm")) or t.startswith("✅") or low in ("y", "k"):
        return ("approve", t)
    return None


def read_decisions() -> list[dict]:
    """Read new owner messages since the stored offset. Returns
    [{"reply_to": <card message_id or None>, "kind": approve|skip|note, "text": ..., "message_id": ...}].
    Messages that are not decisions are ignored. Advances the offset."""
    if not configured():
        return []
    st = _state()
    r = requests.get(f"{API}/getUpdates", params={"offset": st.get("offset", 0), "timeout": 0,
                                                  "allowed_updates": json.dumps(["message"])}, timeout=60)
    r.raise_for_status()
    out: list[dict] = []
    last = st.get("offset", 0)
    for u in r.json().get("result", []):
        last = max(last, u["update_id"] + 1)
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != str(settings.TELEGRAM_CHAT_ID):
            continue
        raw = m.get("text") or ""
        c = classify(raw)
        batch = parse_batch(raw)
        if not c and not batch:
            continue
        reply = m.get("reply_to_message") or {}
        if batch and batch[0]["kind"] == "voice":  # a standing rule, not a decision about a post
            c = ("voice", batch[0]["note"])
        out.append({"reply_to": reply.get("message_id"), "kind": (c or (batch[0]["kind"], ""))[0], "text": raw,
                    "payload": (c[1] if c else raw), "batch": batch, "note": (c[1] if c and c[0] == "voice" else ""),
                    "message_id": m.get("message_id")})
    st["offset"] = last
    _save_state(st)
    return out


def decisions() -> dict[int, tuple[str, str]]:
    """Backward-compatible view: only decisions that were replies to a card."""
    return {d["reply_to"]: (d["kind"], d["payload"]) for d in read_decisions() if d["reply_to"]}


def reply(text: str, to_message_id: int | None = None) -> int | None:
    """Send a message, threaded under the owner's message when possible."""
    if not configured():
        return None
    data = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text[:4000], "disable_web_page_preview": True}
    if to_message_id:
        data["reply_to_message_id"] = to_message_id
        data["allow_sending_without_reply"] = True
    r = requests.post(f"{API}/sendMessage", data=data, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["message_id"]
