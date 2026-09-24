"""Sep 2026: GitHub ran the 08:00 cron at ~13:30 BST and the 20:00 cron after midnight, so
morning posts went out at 00:02/01:11 and the 20 + 21 Sep mornings never went out at all."""
import json
from datetime import datetime

from engine.due import BST, comments_due, due_slots

SLOTS = {"morning": "08:00", "evening": "20:00"}


def _item(q, date, slot, status, **extra):
    d = q / date
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slot}.json").write_text(json.dumps({"status": status, **extra}), encoding="utf-8")


def at(h, m=0, day=20):
    return datetime(2026, 9, day, h, m, tzinfo=BST)


def test_late_morning_run_still_publishes_morning(tmp_path):
    _item(tmp_path, "2026-09-20", "morning", "approved")
    assert due_slots(at(13, 30), tmp_path, SLOTS) == [("2026-09-20", "morning")]


def test_pending_counts_as_due_in_review_mode(tmp_path):
    _item(tmp_path, "2026-09-21", "morning", "pending")
    assert due_slots(at(9, day=21), tmp_path, SLOTS) == [("2026-09-21", "morning")]


def test_nothing_before_slot_time(tmp_path):
    _item(tmp_path, "2026-09-20", "morning", "approved")
    assert due_slots(at(7, 59), tmp_path, SLOTS) == []


def test_after_midnight_never_publishes_next_mornings_post(tmp_path):
    _item(tmp_path, "2026-09-23", "morning", "approved")
    assert due_slots(at(0, 2, day=23), tmp_path, SLOTS) == []


def test_nothing_after_last_hour(tmp_path):
    _item(tmp_path, "2026-09-20", "evening", "approved")
    assert due_slots(at(23, 10), tmp_path, SLOTS) == []


def test_published_and_skipped_are_not_due(tmp_path):
    _item(tmp_path, "2026-09-20", "morning", "published")
    _item(tmp_path, "2026-09-20", "evening", "skipped")
    assert due_slots(at(21), tmp_path, SLOTS) == []


def test_missed_morning_and_evening_both_due_in_order(tmp_path):
    _item(tmp_path, "2026-09-20", "evening", "pending")
    _item(tmp_path, "2026-09-20", "morning", "approved")
    assert due_slots(at(20, 30), tmp_path, SLOTS) == [("2026-09-20", "morning"), ("2026-09-20", "evening")]


def test_failed_item_is_due_so_evergreen_covers_it(tmp_path):
    _item(tmp_path, "2026-09-24", "morning", "failed")
    assert due_slots(at(8, 30, day=24), tmp_path, SLOTS) == [("2026-09-24", "morning")]


def test_empty_slot_does_not_pull_evergreen(tmp_path):
    assert due_slots(at(21), tmp_path, SLOTS) == []


def test_quiz_answer_comment_due_after_delay(tmp_path):
    _item(tmp_path, "2026-09-20", "morning", "published", first_comment="Answer: B",
          published_at="2026-09-20T02:00:00+00:00", comment_delay_minutes=360)
    assert not comments_due(at(13), tmp_path)
    assert comments_due(at(14, 1), tmp_path)
