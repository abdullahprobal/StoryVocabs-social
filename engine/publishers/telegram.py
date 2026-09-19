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


def _preview_text(item) -> str:
    """Build the review message body consistently for new and edited previews."""
    head = (f"🗓 {item.date} · {item.slot} · {item.pillar} · hook={item.hook_style} · score={item.quality_score}\n"
            f"id: {item.id}\n\n")
    tail = ("\n\n— reply to THIS message —\n❌ skip   ✏️ <note> regenerate   ✅ approve\n"
            f"No reply = publishes at {item.slot} slot (REVIEW_MODE={settings.REVIEW_MODE}).")
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


def decisions() -> dict[int, tuple[str, str]]:
    """Read new updates; map replied-to message_id → decision. Advances the stored offset."""
    if not configured():
        return {}
    st = _state()
    r = requests.get(f"{API}/getUpdates", params={"offset": st.get("offset", 0), "timeout": 0, "allowed_updates": json.dumps(["message"])},
                     timeout=60)
    r.raise_for_status()
    out: dict[int, tuple[str, str]] = {}
    last = st.get("offset", 0)
    for u in r.json().get("result", []):
        last = max(last, u["update_id"] + 1)
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != str(settings.TELEGRAM_CHAT_ID):
            continue
        reply = m.get("reply_to_message")
        text = (m.get("text") or "").strip()
        if not reply or not text:
            continue
        low = text.lower()
        if low.startswith(("❌", "skip", "no", "x")):
            out[reply["message_id"]] = ("skip", text)
        elif low.startswith(("✏", "edit", "note", "change", "fix")):
            note = text.split(" ", 1)[1] if " " in text else ""
            out[reply["message_id"]] = ("note", note)
        elif low.startswith(("✅", "ok", "yes", "approve", "go")):
            out[reply["message_id"]] = ("approve", text)
    st["offset"] = last
    _save_state(st)
    return out
