"""Launch QA 2026-09-25: posting blockers found in the audit."""
import json
from datetime import datetime

import pytest

from engine.publishers.telegram import classify, parse_batch
from engine import settings


@pytest.mark.parametrize("text", ["don’t post", "Don’t approve this", "not ok", "not good"])
def test_phone_apostrophe_and_not_are_refusals(text):
    assert classify(text)[0] == "skip"
    assert parse_batch(text)[0]["kind"] == "skip"


def test_offer_facts_carry_live_puja_prices():
    facts = json.loads((settings.PROJECT_DIR / "facts.json").read_text(encoding="utf-8"))
    puja = next(o for o in facts["current_offers"] if o["code"] == "PUJA2026")
    assert puja["prices_bdt"] == {"pro_1m": 225, "pro_3m": 600, "pro_6m": 1125, "lifetime": 2000}


def test_pay_easy_never_quotes_regular_prices_during_puja(monkeypatch):
    from engine.writers import pillars
    seen = {}

    def fake_call_json(system, prompt, model, **kw):
        seen["prompt"] = prompt
        return model(headline_bn="পূজার অফার", body_bn="লাইফটাইম এখন অর্ধেক দামে।")
    monkeypatch.setattr(pillars, "call_json", fake_call_json)
    # ISO week 39 (25 Sep) maps to pay_easy in a pay_easy-only rotation
    post = pillars.write_offer("2026-09-25", {"offer_rotation": ["pay_easy"]})
    assert post.kind == "puja_offer" and "৳2,000" in seen["prompt"]
    post = pillars.write_offer("2026-10-28", {"offer_rotation": ["pay_easy"]})
    assert post.kind == "pay_easy"


def test_missed_slot_counts_as_done_for_the_scheduler():
    from engine.due import DONE
    assert "missed" in DONE
