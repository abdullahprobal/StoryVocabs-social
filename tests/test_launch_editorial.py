import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from engine import due, publish


def test_launch_pause_blocks_existing_queue(monkeypatch, tmp_path):
    monkeypatch.setattr(due, "paused_dates", lambda: {"2026-10-10": "launch content"})
    path = tmp_path / "2026-10-10" / "morning.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"status": "approved"}), encoding="utf-8")
    assert due.due_slots(datetime(2026, 10, 10, 10, tzinfo=due.BST), tmp_path) == []


def test_manual_invocation_cannot_fall_back_during_launch_pause(monkeypatch):
    monkeypatch.setattr(publish, "load_holidays", lambda: {"skip_dates": {"2026-10-10": "launch"}})
    monkeypatch.setattr(publish, "load_item", lambda path: pytest.fail("must stop before reading or replacing queue"))
    assert publish.run_slot("2026-10-10", "morning") == 0


@pytest.mark.parametrize("mode", ["review", "autopilot"])
@pytest.mark.parametrize("pillar", ["offer", "in_app"])
def test_sales_and_product_posts_require_explicit_review(monkeypatch, mode, pillar):
    monkeypatch.setattr(publish, "load_holidays", lambda: {})
    monkeypatch.setattr(publish.settings, "REVIEW_MODE", mode)
    monkeypatch.setattr(publish.telegram, "configured", lambda: False)
    monkeypatch.setattr(publish.telegram, "notify", lambda text: None)
    item = SimpleNamespace(status="pending", pillar=pillar, date="2026-10-17", slot="morning", hook_style="question")
    monkeypatch.setattr(publish, "load_item", lambda path: item)
    monkeypatch.setattr(publish, "publish_item", lambda item: pytest.fail("unreviewed creative must not publish"))
    assert publish.run_slot(item.date, item.slot) == 0


def test_review_skip_cannot_trigger_evergreen_replacement(monkeypatch):
    monkeypatch.setattr(publish, "load_holidays", lambda: {})
    monkeypatch.setattr(publish.telegram, "configured", lambda: True)
    reads = iter([SimpleNamespace(status="pending"), SimpleNamespace(status="skipped")])
    monkeypatch.setattr(publish, "load_item", lambda path: next(reads))
    from engine import review
    monkeypatch.setattr(review, "apply_decisions", lambda: [])
    monkeypatch.setattr(publish, "pick_evergreen", lambda *args: pytest.fail("owner skip must stop publishing"))
    assert publish.run_slot("2026-10-17", "morning") == 0
