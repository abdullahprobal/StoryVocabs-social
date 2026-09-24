"""Decides WHAT to make for a given date: slot, pillar, topic group, hook
style — from strategy.json + data/holidays.json.

    from engine.planner import plan_for_date
    for p in plan_for_date("2026-09-20"): ...
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime

from engine import settings

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def load_strategy() -> dict:
    return json.loads(settings.STRATEGY_FILE.read_text(encoding="utf-8"))


def save_strategy(strategy: dict) -> None:
    settings.STRATEGY_FILE.write_text(json.dumps(strategy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_holidays() -> dict:
    if not settings.HOLIDAYS_FILE.exists():
        return {}
    return json.loads(settings.HOLIDAYS_FILE.read_text(encoding="utf-8"))


@dataclass
class PlanItem:
    date: str
    slot: str            # morning | evening
    pillar: str
    time_bst: str        # "08:00"
    topic_group: str = ""
    hook_style: str = ""
    weekday: str = ""
    note: str = ""
    extras: dict = field(default_factory=dict)


def _in_ramadan(d: date, holidays: dict) -> bool:
    for w in holidays.get("ramadan_windows", []):
        try:
            s = datetime.strptime(w["start"], "%Y-%m-%d").date()
            e = datetime.strptime(w["end"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if s <= d <= e:
            return True
    return False


PILLAR_HOOKS = {
    # story pillars may open mid-scene; the others must stay literal about the word
    "news_word": ["question", "bold_true", "number", "exam_angle", "mistake"], "story60": None,
    "quiz": ["question", "mistake", "exam_angle"],
    "confusables": ["mistake", "question", "exam_angle", "bold_true"],
    "in_app": ["question", "bold_true", "exam_angle"],
    "offer": ["question", "bold_true", "exam_angle"],
}


def pick_hook_style(strategy: dict, rng: random.Random | None = None, pillar: str = "") -> str:
    rng = rng or random.Random()
    styles = strategy.get("hook_styles", {})
    if not styles:
        return "question"
    allowed = PILLAR_HOOKS.get(pillar)
    if pillar not in PILLAR_HOOKS:
        try:
            from engine.writers.generic import spec_for
            allowed = (spec_for(pillar) or {}).get("hook_styles") or ["question", "bold_true", "exam_angle", "number"]
        except Exception:  # noqa: BLE001
            allowed = None
    names = [n for n in styles if not allowed or n in allowed] or list(styles)
    weights = [max(0.05, float(styles[n].get("weight", 1.0))) for n in names]
    return rng.choices(names, weights=weights, k=1)[0]


def plan_for_date(date_str: str, strategy: dict | None = None, holidays: dict | None = None,
                  seed: int | None = None) -> list[PlanItem]:
    """Return the posts to make on date_str (may be empty on skip days)."""
    strategy = strategy or load_strategy()
    holidays = holidays if holidays is not None else load_holidays()
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    weekday = WEEKDAYS[d.weekday()]
    rng = random.Random(seed if seed is not None else int(d.strftime("%Y%m%d")))

    if date_str in holidays.get("skip_dates", {}):
        return []

    ramadan = _in_ramadan(d, holidays)
    slot_times = dict(strategy["slots"].get("ramadan", {})) if ramadan else {
        k: v for k, v in strategy["slots"].items() if isinstance(v, str)}

    # date_overrides: one-off days (e.g. a launch burst) that replace the weekday calendar
    entries = strategy.get("date_overrides", {}).get(date_str) or strategy["calendar"].get(weekday, [])
    if date_str in holidays.get("single_evening_post_dates", {}):
        entries = [{"slot": "evening", "pillar": "quiz"}]

    items: list[PlanItem] = []
    for e in entries:
        pillar = e["pillar"]
        if pillar == "in_app" and not strategy.get("in_app_screens"):
            pillar = "confusables"   # no screenshots yet — keep the day useful
        slot = e.get("slot", "morning")
        items.append(PlanItem(
            date=date_str, slot=slot, pillar=pillar,
            time_bst=slot_times.get(slot, "08:00"),
            topic_group=e.get("topic_group", ""),
            hook_style=pick_hook_style(strategy, rng, pillar),
            weekday=weekday,
            note="ramadan" if ramadan else "",
            extras={k: v for k, v in e.items() if k not in ("slot", "pillar", "topic_group")},
        ))
    return items


def slot_datetime_bst(date_str: str, time_bst: str) -> datetime:
    hh, mm = time_bst.split(":")
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.replace(hour=int(hh), minute=int(mm), tzinfo=settings.BST)
