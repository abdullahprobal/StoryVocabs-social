import json
from pathlib import Path

from engine import settings
from engine.publishers import telegram
from render import image_renderer as R
from tests.fixtures_story import NEWS_POST


def test_decision_parser(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram, "STATE", tmp_path / "tg.json")

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": [
                {"update_id": 1, "message": {"chat": {"id": 42}, "text": "❌ too dry", "reply_to_message": {"message_id": 10}}},
                {"update_id": 2, "message": {"chat": {"id": 42}, "text": "edit: make hook a question", "reply_to_message": {"message_id": 11}}},
                {"update_id": 3, "message": {"chat": {"id": 42}, "text": "ok", "reply_to_message": {"message_id": 12}}},
                {"update_id": 4, "message": {"chat": {"id": 99}, "text": "❌", "reply_to_message": {"message_id": 13}}},
                {"update_id": 5, "message": {"chat": {"id": 42}, "text": "hello (no reply)"}},
            ]}

    monkeypatch.setattr(telegram.requests, "get", lambda *a, **k: Resp())
    d = telegram.decisions()
    assert d[10][0] == "skip" and d[11] == ("note", "make hook a question") and d[12][0] == "approve"
    assert 13 not in d
    assert json.loads((tmp_path / "tg.json").read_text())["offset"] == 6


def test_ruby_and_hero_markup():
    html = R.ruby("The [[candor|অকপটতা]] of the board")
    assert 'class="ruby"' in html and "অকপটতা" in html and "[[" not in html
    assert '<span class="mark">candor</span>' in R.mark_hero("Board shows [[candor]] today")


def test_story_post_renders_all_slides(tmp_path):
    paths = R.render_story_post(NEWS_POST, tmp_path, "2026-09-19")
    assert len(paths) == 1 + 1 + 3 + 1
    from engine import gates
    gates.render_check(paths)
    story = R.render_story_card(R.mark_hero(NEWS_POST.headline_en), NEWS_POST.headline_bn, "আজকের খবরে", tmp_path)
    gates.render_check([story], size=settings.STORY_CANVAS)


def test_classify_accepts_plain_words():
    c = telegram.classify
    assert c("approve")[0] == "approve" and c("✅")[0] == "approve" and c("ok go")[0] == "approve"
    assert c("skip")[0] == "skip" and c("❌ too dry")[0] == "skip"
    assert c("edit: make it a question") == ("note", "make it a question")
    assert c("✏️ shorter hook") == ("note", "shorter hook")
    assert c("hello?") is None


def test_plain_decision_targets_newest_pending_card(monkeypatch, tmp_path):
    from engine import review, settings
    from engine.contracts import QueueItem
    from engine.generate import save_item
    monkeypatch.setattr(settings, "QUEUE_DIR", tmp_path)
    for i, (d, mid) in enumerate([("2026-09-19", 40), ("2026-09-20", 44)]):
        save_item(QueueItem(id=f"x{i}", date=d, slot="morning", pillar="quiz", content={}, telegram_message_id=mid),
                  tmp_path / d / "morning.json")
    replies = []
    monkeypatch.setattr(review.telegram, "reply", lambda text, to=None: replies.append(text) or 1)
    regen = review.apply_decisions([{"reply_to": None, "kind": "approve", "text": "approve", "message_id": 50}])
    assert regen == []
    a = json.loads((tmp_path / "2026-09-20" / "morning.json").read_text(encoding="utf-8"))
    b = json.loads((tmp_path / "2026-09-19" / "morning.json").read_text(encoding="utf-8"))
    assert a["status"] == "approved" and b["status"] == "pending"
    assert replies and replies[0].startswith("✅ Approved")
    regen = review.apply_decisions([{"reply_to": 40, "kind": "note", "text": "shorter", "message_id": 51}])
    assert len(regen) == 1 and regen[0][1].review_note == "shorter"
