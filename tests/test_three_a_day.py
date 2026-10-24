"""3 posts a day (2026-10-02): every weekday plans 3 slots, nothing hardcodes morning/evening,
gaps are refilled before their slot, and a near-miss post beats an empty slot."""
import json
from datetime import datetime

import pytest

from engine import gates, settings
from engine import generate as gen
from engine.contracts import QueueItem
from engine.due import BST, due_slots, missing_slots
from engine.planner import PlanItem, plan_for_date


@pytest.mark.parametrize("date", ["2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06",
                                  "2026-10-07", "2026-10-08", "2026-10-09"])
def test_every_weekday_plans_three_posts(date):
    plans = plan_for_date(date, holidays={})
    assert [p.slot for p in plans] == ["morning", "noon", "evening"]
    assert [p.time_bst for p in plans] == ["08:00", "13:00", "20:00"]


def test_every_planned_pillar_can_be_written():
    strategy = json.loads(settings.STRATEGY_FILE.read_text(encoding="utf-8"))
    pillars = {e["pillar"] for day in strategy["calendar"].values() for e in day}
    from engine.writers.generic import spec_for
    assert all(p in gen.CONTENT_TYPES or spec_for(p) for p in pillars), pillars


def test_noon_is_a_valid_slot_with_labels():
    item = QueueItem(id="x", date="2026-10-03", slot="noon", pillar="quiz", content={})
    assert item.slot == "noon"
    assert settings.slot_label("noon") == "1:00 PM"
    assert settings.slot_label("evening") == "8:00 PM"
    assert settings.slot_order("morning") < settings.slot_order("noon") < settings.slot_order("evening")


def _write(queue, date, slot, status):
    (queue / date).mkdir(parents=True, exist_ok=True)
    (queue / date / f"{slot}.json").write_text(json.dumps({"status": status}), encoding="utf-8")


def test_noon_slot_is_due_after_one_pm(tmp_path):
    _write(tmp_path, "2026-10-03", "noon", "pending")
    slots = {"morning": "08:00", "noon": "13:00", "evening": "20:00"}
    assert due_slots(datetime(2026, 10, 3, 12, 50, tzinfo=BST), tmp_path, slots) == []
    assert due_slots(datetime(2026, 10, 3, 13, 23, tzinfo=BST), tmp_path, slots) == [("2026-10-03", "noon")]


def test_repair_finds_failed_and_missing_slots_but_not_long_past_ones(tmp_path):
    slots = {"morning": "08:00", "noon": "13:00", "evening": "20:00"}
    _write(tmp_path, "2026-10-03", "noon", "failed")
    _write(tmp_path, "2026-10-03", "evening", "pending")
    for slot in slots:
        _write(tmp_path, "2026-10-04", slot, "pending")
    gaps = missing_slots(datetime(2026, 10, 3, 12, 0, tzinfo=BST), tmp_path, slots)
    # morning 08:00 is 4 h past (> 3 h grace): left alone; noon failed: remade
    assert gaps == [("2026-10-03", "noon")]


def test_fill_after_midnight_still_covers_today():
    late = datetime(2026, 10, 2, 1, 30, tzinfo=BST)
    assert gen.fill_dates(late) == ["2026-10-02", "2026-10-03", "2026-10-04"]
    assert gen.review_date(late) == "2026-10-02"
    assert gen.review_date(datetime(2026, 10, 2, 20, 17, tzinfo=BST)) == "2026-10-03"


def test_quiz_answer_lands_before_the_last_publish_run():
    for slot, time in (("morning", "08:00"), ("noon", "13:00"), ("evening", "20:00")):
        plan = PlanItem(date="2026-10-03", slot=slot, pillar="quiz", time_bst=time)
        h, m = map(int, time.split(":"))
        assert h * 60 + m + gen.quiz_answer_delay(plan) <= 21 * 60 + 30


class _Content:
    def model_dump(self):
        return {}


class _Verdict:
    def __init__(self, score, factual=False):
        self.score, self.hook_score, self.bangla_ok = score, 9.0, True
        self.factual_error, self.forced_words, self.issues, self.improved_hook = factual, [], ["flat ending"], ""


def _stub_pipeline(monkeypatch, scores, factual=False):
    """build_item with every external step stubbed; the critic returns `scores` in order."""
    from engine.caption import Caption
    seq = iter(scores)
    monkeypatch.setattr(gen, "make_content", lambda *a, **k: _Content())
    monkeypatch.setattr(gen, "summarize", lambda c: "summary")
    monkeypatch.setattr(gen, "write_caption", lambda *a, **k: Caption.model_construct(body="b", comment_prompt=""))
    monkeypatch.setattr(gen, "assemble", lambda *a, **k: ("hook\nbody", "hook\nbody", "https://x"))
    for name in ("banned_claims", "caption_shape", "register", "render_check"):
        monkeypatch.setattr(gates, name, lambda *a, **k: None)
    monkeypatch.setattr(gates, "critic", lambda *a, **k: _Verdict(next(seq), factual))
    monkeypatch.setattr(gen, "render_content", lambda c, out, d: (["a.png"], "s.png"))
    monkeypatch.setattr(gen, "words_used", lambda c: [])


def test_best_near_miss_is_kept_when_nothing_reaches_the_pass_mark(monkeypatch):
    _stub_pipeline(monkeypatch, [7.0, 7.5, 6.0, 7.0])
    plan = PlanItem(date="2026-10-03", slot="noon", pillar="confusables", time_bst="13:00", hook_style="question")
    item = gen.build_item(plan, {"hook_styles": {}}, dry_run=True)
    assert item.status == "pending" and item.quality_score == 7.5


def test_a_passing_attempt_wins_over_an_earlier_near_miss(monkeypatch):
    _stub_pipeline(monkeypatch, [7.0, 8.5])
    plan = PlanItem(date="2026-10-03", slot="noon", pillar="confusables", time_bst="13:00", hook_style="question")
    item = gen.build_item(plan, {"hook_styles": {}}, dry_run=True)
    assert item.quality_score == 8.5 and item.attempts == 2


def test_factual_errors_are_never_kept(monkeypatch):
    _stub_pipeline(monkeypatch, [9.0] * 4, factual=True)
    plan = PlanItem(date="2026-10-03", slot="noon", pillar="confusables", time_bst="13:00", hook_style="question")
    item = gen.build_item(plan, {"hook_styles": {}}, dry_run=True)
    assert item.status == "failed"


def test_evergreen_count_ignores_used_backups(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EVERGREEN_DIR", tmp_path)
    item = QueueItem(id="e1", date="2029-01-01", slot="morning", pillar="quiz", content={})
    (tmp_path / "quiz_e1.json").write_text(item.model_dump_json(), encoding="utf-8")
    (tmp_path / "quiz_e2.used").write_text(item.model_dump_json(), encoding="utf-8")
    assert gen.evergreen_left() == 1
