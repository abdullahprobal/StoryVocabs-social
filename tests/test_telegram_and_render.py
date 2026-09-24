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
    from engine import lineup, review, settings
    from engine.contracts import QueueItem
    from engine.generate import save_item
    monkeypatch.setattr(settings, "QUEUE_DIR", tmp_path)
    monkeypatch.setattr(lineup, "STATE", tmp_path / "lineup.json")   # no real lineup in play
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
    assert replies and replies[0].startswith("✅ ")
    regen = review.apply_decisions([{"reply_to": 40, "kind": "note", "text": "shorter", "message_id": 51}])
    assert len(regen) == 1 and regen[0][1].review_note == "shorter"


def test_parse_batch_covers_lineup_replies():
    pb = telegram.parse_batch
    assert pb("approve all") == [{"kind": "approve", "numbers": "all", "note": ""}]
    assert pb("skip 2") == [{"kind": "skip", "numbers": [2], "note": ""}]
    assert pb("1 ok, 2 skip") == [{"kind": "approve", "numbers": [1], "note": ""}, {"kind": "skip", "numbers": [2], "note": ""}]
    assert pb("edit 3: shorter hook") == [{"kind": "note", "numbers": [3], "note": "shorter hook"}]
    assert pb("approve")[0]["numbers"] is None
    assert pb("hello") == []


def test_lineup_numbers_resolve_to_items(monkeypatch, tmp_path):
    from engine import lineup, review, settings
    from engine.contracts import QueueItem
    from engine.generate import save_item
    monkeypatch.setattr(settings, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    monkeypatch.setattr(lineup, "STATE", tmp_path / "lineup.json")
    a = tmp_path / "queue" / "2026-09-22" / "morning.json"
    b = tmp_path / "queue" / "2026-09-22" / "evening.json"
    save_item(QueueItem(id="m", date="2026-09-22", slot="morning", pillar="quiz", content={}, telegram_message_id=70, caption_fb="hook m"), a)
    save_item(QueueItem(id="e", date="2026-09-22", slot="evening", pillar="offer", content={}, telegram_message_id=71, caption_fb="hook e"), b)
    sent = []
    monkeypatch.setattr(lineup.telegram, "notify", lambda text: sent.append(text) or 1)
    monkeypatch.setattr(lineup.telegram, "send_preview", lambda it, number=None: 100 + number)
    assert lineup.send_lineup("2026-09-22") == 2
    assert "1. 8:00 AM" in sent[-1] and "2. 8:00 PM" in sent[-1]
    replies = []
    monkeypatch.setattr(review.telegram, "reply", lambda text, to=None: replies.append(text) or 1)
    review.apply_decisions([{"reply_to": None, "kind": "skip", "text": "1 ok, 2 skip",
                             "batch": telegram.parse_batch("1 ok, 2 skip"), "message_id": 5}])
    assert json.loads(a.read_text(encoding="utf-8"))["status"] == "approved"
    assert json.loads(b.read_text(encoding="utf-8"))["status"] == "skipped"
    assert replies and "✅" in replies[-1] and "❌" in replies[-1]


def test_single_image_preview_uses_send_photo(monkeypatch, tmp_path):
    """sendMediaGroup rejects 1 item; the owner got captions with no image for quiz posts."""
    from types import SimpleNamespace
    from engine.publishers import telegram as T
    img = tmp_path / "slide.png"
    img.write_bytes(b"png")
    calls = []

    def fake_post(url, data=None, files=None, timeout=None):
        calls.append(url.rsplit("/", 1)[1])
        return SimpleNamespace(ok=True, status_code=200, text="", raise_for_status=lambda: None,
                               json=lambda: {"result": {"message_id": 7}})
    monkeypatch.setattr(T.requests, "post", fake_post)
    monkeypatch.setattr(T, "_preview_text", lambda item, number=None: "caption")
    item = SimpleNamespace(media=[str(img)], media_urls=[])
    assert T.send_preview(item) == 7
    assert calls == ["sendPhoto", "sendMessage"]
