"""Refresh queued Telegram previews after a caption-format change.

Run locally with the review bot credentials in ``.env``. The script only
prints queue ids and statuses; it never prints tokens or chat identifiers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import settings
from engine.contracts import QueueItem
from engine.publishers import telegram


def main() -> int:
    if not telegram.configured():
        print("Telegram is not configured")
        return 1

    refreshed = 0
    for path in sorted(settings.QUEUE_DIR.glob("*/*.json")):
        try:
            item = QueueItem.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not item.telegram_message_id:
            continue
        telegram.edit_preview(item)
        print(f"refreshed {item.date} {item.slot} {item.id}")
        refreshed += 1
    print(f"refreshed_count={refreshed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
