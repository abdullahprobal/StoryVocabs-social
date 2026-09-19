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


PILLAR_LABELS = {"news_word": "News Word", "quiz": "Quiz", "confusables": "Confusables",
                 "in_app": "In the App", "story60": "Story in 60s", "offer": "Community / Offer"}


def _preview_text(item) -> str:
    """Review card: what a reader will see, then how to decide. No internal ids or scores."""
    from datetime import datetime
    try:
        day = datetime.strptime(item.date, "%Y-%m-%d").strftime("%a %d %b")
    except ValueError:
        day = item.date
    when = {"morning": "8:00 AM", "evening": "8:00 PM"}.get(item.slot, item.slot)
    slides = f"{len(item.media)} slide{'s' if len(item.media) != 1 else ''}"
    head = f"📋 Review · {day} · {when} · {PILLAR_LABELS.get(item.pillar, item.pillar)} · {slides}\n\n"
    if settings.REVIEW_MODE == "manual":
        rule = "Nothing is posted until you reply ✅ to this message."
    elif settings.REVIEW_MODE == "review":
        rule = f"Posts automatically at {when} unless you reply ❌."
    else:
        rule = "Autopilot is on; this is a copy of what will post."
    tail = ("\n\n————————————\n"
            "Reply to this message:  ✅ approve  ·  ❌ skip  ·  ✏️ your note (regenerates)\n" + rule)
    return (head + item.caption_fb + tail)[:4000]


def send_preview(item) -> int:
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
                                                  "text": _preview_text(item),
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
        c = classify(m.get("text") or "")
        if not c:
            continue
        reply = m.get("reply_to_message") or {}
        out.append({"reply_to": reply.get("message_id"), "kind": c[0], "text": c[1], "message_id": m.get("message_id")})
    st["offset"] = last
    _save_state(st)
    return out


def decisions() -> dict[int, tuple[str, str]]:
    """Backward-compatible view: only decisions that were replies to a card."""
    return {d["reply_to"]: (d["kind"], d["text"]) for d in read_decisions() if d["reply_to"]}


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
