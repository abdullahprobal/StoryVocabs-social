"""Word supply: vendored packs (data/word_packs.json) + usage tracker
(state/word_usage_tracker.json). A word is never featured more than
max_word_uses_per_year times and never twice within min_days_between_same_word.
"""
from __future__ import annotations

import json
import random
from datetime import datetime

from engine import settings
from engine.contracts import Word

TRACKER = settings.STATE_DIR / "word_usage_tracker.json"

_cache: list[dict] | None = None


def all_words() -> list[dict]:
    global _cache
    if _cache is None:
        data = json.loads(settings.WORD_PACKS_FILE.read_text(encoding="utf-8"))
        seen, out = set(), []
        for pack in data["packs"]:
            for w in pack.get("words", []):
                key = w["word"].strip().lower()
                if key in seen or not w.get("bangla"):
                    continue
                seen.add(key)
                out.append(w)
        _cache = out
    return _cache


def load_tracker() -> dict:
    if TRACKER.exists():
        try:
            return json.loads(TRACKER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_tracker(t: dict) -> None:
    TRACKER.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")


def is_available(w: dict, tracker: dict, date_str: str, strategy: dict) -> bool:
    rec = tracker.get(w["word"].lower())
    if not rec:
        return True
    year = date_str[:4]
    if rec.get(year, 0) >= strategy.get("max_word_uses_per_year", 3):
        return False
    gap = strategy.get("min_days_between_same_word", 120)
    today = datetime.strptime(date_str, "%Y-%m-%d")
    for d in rec.get("dates", []):
        try:
            if abs((today - datetime.strptime(d, "%Y-%m-%d")).days) < gap:
                return False
        except ValueError:
            continue
    return True


def mark_used(words: list[str], date_str: str) -> None:
    t = load_tracker()
    year = date_str[:4]
    for w in words:
        rec = t.setdefault(w.lower(), {})
        rec[year] = rec.get(year, 0) + 1
        rec.setdefault("dates", []).append(date_str)
    save_tracker(t)


def candidates(date_str: str, strategy: dict, count: int = 30, difficulty: str | None = None,
               seed: int | None = None, pos: str | None = None) -> list[dict]:
    """A shuffled pool of fresh candidate words for the LLM to choose from."""
    tracker = load_tracker()
    pool = [w for w in all_words() if is_available(w, tracker, date_str, strategy)]
    if difficulty:
        pool = [w for w in pool if w.get("difficulty") == difficulty] or pool
    if pos:
        pool = [w for w in pool if w.get("pos") == pos] or pool
    rng = random.Random(seed if seed is not None else int(date_str.replace("-", "")))
    rng.shuffle(pool)
    return pool[:count]


def by_name(name: str) -> dict | None:
    key = name.strip().lower()
    for w in all_words():
        if w["word"].lower() == key:
            return w
    return None


def to_card(w: dict, gloss_bn: str = "", meaning_bn: str = "", meaning_en: str = "",
            example: str = "", phonetic: str = "") -> Word:
    """Build a Word card from pack data, letting LLM-provided short fields override."""
    bangla = (w.get("bangla") or "").strip()
    short_bn = gloss_bn or bangla.split(",")[0].split("।")[0].strip()
    return Word(
        word=w["word"],
        pos=w.get("pos") or w.get("partOfSpeech") or "",
        difficulty=w.get("difficulty") if w.get("difficulty") in ("Beginner", "Intermediate", "Advanced") else "Intermediate",
        phonetic=phonetic,
        gloss_bn=short_bn,
        meaning_bn=meaning_bn or bangla,
        meaning_en=meaning_en or (w.get("meaning") or ""),
        example=example or _bold(w.get("sentence") or "", w["word"]),
        synonym=w.get("synonym") or "",
        antonym=w.get("antonym") or "",
    )


def _bold(sentence: str, word: str) -> str:
    import re
    if not sentence:
        return ""
    return re.sub(rf"\b({re.escape(word)}\w*)", r"<b>\1</b>", sentence, count=1, flags=re.I)


def candidate_lines(words: list[dict]) -> str:
    return "\n".join(
        f"{i}. {w['word']} ({w.get('pos','')}, {w.get('difficulty','')}) — {w.get('bangla','')[:60]} — {w.get('meaning','')[:90]}"
        for i, w in enumerate(words, 1)
    )
