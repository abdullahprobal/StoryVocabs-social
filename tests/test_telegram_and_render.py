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
