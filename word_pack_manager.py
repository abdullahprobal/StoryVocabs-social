"""Manages word pack loading, session-isolated candidate selection, and usage tracking."""

import json
import re
import random
from pathlib import Path
from datetime import datetime


TRACKER_FILE = Path(__file__).parent / "word_usage_tracker.json"
MAX_USAGE_PER_YEAR = 3

POST_SCHEDULE = {
    "post_1": {"word_count": 3, "new_words": 3},
    "post_2": {"word_count": 5, "revise_from": "post_1", "revise_count": 3, "new_words": 2},
    "post_3": {"word_count": 3, "new_words": 3},
    "post_4": {"word_count": 5, "revise_from": "post_3", "revise_count": 3, "new_words": 2},
}


def load_word_packs_from_js():
    """Parse the app's JS word pack files and return all words."""
    app_data = Path(__file__).parent.parent / "Story-Vocabulary app" / "frontend" / "src" / "data"
    all_words = []

    for js_file in ["wordPacks.js", "wordPacksGenerated.js"]:
        filepath = app_data / js_file
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8")
        start = content.find('[')
        if start == -1:
            continue
        depth = 0
        end = start
        for i, ch in enumerate(content[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        json_str = content[start:end]
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        try:
            packs = json.loads(json_str)
            for pack in packs:
                for word in pack.get("words", []):
                    word["_pack_id"] = pack.get("id")
                    word["_pack_title"] = pack.get("title", "")
                    word["_difficulty"] = pack.get("difficulty", "Intermediate")
                all_words.extend(pack.get("words", []))
            print(f"   {js_file}: {len(packs)} packs, {sum(len(p.get('words', [])) for p in packs)} words")
        except json.JSONDecodeError as e:
            print(f"   JSON error in {js_file}: {e}")
    return all_words


def load_tracker():
    """Load word usage tracker."""
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_tracker(tracker):
    """Save word usage tracker."""
    TRACKER_FILE.write_text(json.dumps(tracker, indent=2, ensure_ascii=False), encoding="utf-8")


def get_usage_count(tracker, word, year):
    """Get how many times a word was used this year (deduplicated by date)."""
    entry = tracker.get(word.lower(), {})
    dates = entry.get("dates", [])
    # Count unique dates in this year only — fixes double-counting from revision posts
    unique_dates_this_year = set(d for d in dates if d.startswith(str(year)))
    return len(unique_dates_this_year)


def mark_used(tracker, words, date_str):
    """Mark words as used on a date. Each word is recorded once per date (dedup fix).
    
    Previously, revision words appeared in both Post 1 and Post 2, causing them to be
    marked twice per day and exceed MAX_USAGE_PER_YEAR prematurely. Now we record
    each word only once per date regardless of how many posts it appears in.
    """
    year = date_str[:4]
    for w in words:
        word_key = w["word"].lower()
        if word_key not in tracker:
            tracker[word_key] = {}
        if "dates" not in tracker[word_key]:
            tracker[word_key]["dates"] = []

        # Only add the date once per word per date (dedup)
        if date_str not in tracker[word_key]["dates"]:
            tracker[word_key]["dates"].append(date_str)

        # Recompute year count from unique dates (clean up legacy over-counts)
        unique_this_year = len(set(d for d in tracker[word_key]["dates"] if d.startswith(year)))
        tracker[word_key][str(year)] = unique_this_year

    return tracker


def get_available_words(all_words, tracker, year):
    """Get words that haven't been used MAX_USAGE_PER_YEAR unique dates this year."""
    available = []
    for w in all_words:
        count = get_usage_count(tracker, w["word"], year)
        if count < MAX_USAGE_PER_YEAR:
            available.append(w)
    return available


def get_candidate_words(all_words, session=1, count=30):
    """Return a session-isolated pool of candidate words for word-topic alignment.

    Each session gets a distinct non-overlapping slice of the available word pool.
    The slice is based on (day_number * count + (session-1) * count) % len(available),
    so Session 1 and Session 2 on the same day use completely different words.

    Args:
        all_words: Full word list from word packs.
        session: Session number (1-based). Each session gets a distinct slice.
        count: How many candidate words to return (default 30 for alignment).

    Returns:
        List of word dicts, deduplicated and usage-filtered.
    """
    today = datetime.now()
    reference_date = datetime(2026, 3, 29)
    day_number = (today - reference_date).days

    tracker = load_tracker()
    year = today.strftime("%Y")
    date_str = today.strftime("%Y-%m-%d")

    available = get_available_words(all_words, tracker, year)

    if len(available) < count:
        print(f"   WARNING: Only {len(available)} words available (need {count}), using all + extras")
        # Pad with least-used words from full list
        used_words = set(w["word"].lower() for w in available)
        extras = [w for w in all_words if w["word"].lower() not in used_words]
        available = available + extras

    total = len(available)

    # Session-isolated offset: day_number seeds the day, session shifts within the day
    start = ((day_number * count) + ((session - 1) * count)) % total
    end = start + count

    if end <= total:
        candidates = available[start:end]
    else:
        candidates = available[start:] + available[:end - total]

    print(f"   Date: {date_str} (Day {day_number + 1}), Session {session}")
    print(f"   Candidate pool: {len(candidates)} words (positions {start}–{start + len(candidates) - 1})")
    print(f"   Words: {', '.join(w['word'] for w in candidates[:10])}{'...' if len(candidates) > 10 else ''}")

    return candidates


def build_word_sets_from_alignment(topic_a_aligned, topic_b_aligned):
    """Build post word sets from the alignment result.

    Args:
        topic_a_aligned: dict with keys 'short' (3 words) and 'new_for_long' (2 words)
        topic_b_aligned: dict with keys 'short' (3 words) and 'new_for_long' (2 words)

    Returns:
        dict with post_1_words, post_2_words, post_3_words, post_4_words, all_unique_words
    """
    post_1_words = topic_a_aligned["short"]       # 3 words
    post_2_new   = topic_a_aligned["new_for_long"] # 2 new
    post_3_words = topic_b_aligned["short"]        # 3 words
    post_4_new   = topic_b_aligned["new_for_long"] # 2 new

    post_2_words = post_1_words[:3] + post_2_new   # 3 revise + 2 new = 5
    post_4_words = post_3_words[:3] + post_4_new   # 3 revise + 2 new = 5

    all_unique = list({w["word"].lower(): w for w in
                       post_1_words + post_2_new + post_3_words + post_4_new}.values())

    print(f"   Post 1: {', '.join(w['word'] for w in post_1_words)}")
    print(f"   Post 2: {', '.join(w['word'] for w in post_2_words)}")
    print(f"   Post 3: {', '.join(w['word'] for w in post_3_words)}")
    print(f"   Post 4: {', '.join(w['word'] for w in post_4_words)}")

    return {
        "post_1_words": post_1_words,
        "post_2_words": post_2_words,
        "post_3_words": post_3_words,
        "post_4_words": post_4_words,
        "all_unique_words": all_unique,
        "post_2_new_words": post_2_new,
        "post_4_new_words": post_4_new,
    }


# ─── Legacy function kept for compatibility ────────────────────────────────────

def get_daily_word_sets(all_words):
    """Legacy: Get word sets for all 4 posts of the day (session=1).

    This is kept for compatibility. New code should use get_candidate_words() +
    select_words_for_session() + build_word_sets_from_alignment() instead.
    """
    today = datetime.now()
    reference_date = datetime(2026, 3, 29)
    day_number = (today - reference_date).days

    total = len(all_words)
    if total == 0:
        return None

    tracker = load_tracker()
    year = today.strftime("%Y")
    date_str = today.strftime("%Y-%m-%d")

    available = get_available_words(all_words, tracker, year)

    if len(available) < 10:
        print(f"   WARNING: Only {len(available)} words available (need 10)")
        available = available + (all_words[:max(0, 10 - len(available))])

    start = (day_number * 10) % len(available)
    end = start + 10
    if end <= len(available):
        day_pool = available[start:end]
    else:
        day_pool = available[start:] + available[:end - len(available)]

    if len(day_pool) < 10:
        day_pool = day_pool + all_words[:10 - len(day_pool)]

    post_1_words = day_pool[:3]
    post_2_new = day_pool[3:5]
    post_3_words = day_pool[5:8]
    post_4_new = day_pool[8:10]

    post_2_words = post_1_words[:3] + post_2_new
    post_4_words = post_3_words[:3] + post_4_new

    print(f"   Date: {date_str} (Day {day_number + 1})")
    print(f"   Post 1: {len(post_1_words)} words — {', '.join(w['word'] for w in post_1_words)}")
    print(f"   Post 2: {len(post_2_words)} words — {', '.join(w['word'] for w in post_2_words)}")
    print(f"   Post 3: {len(post_3_words)} words — {', '.join(w['word'] for w in post_3_words)}")
    print(f"   Post 4: {len(post_4_words)} words — {', '.join(w['word'] for w in post_4_words)}")

    return {
        "post_1_words": post_1_words,
        "post_2_words": post_2_words,
        "post_3_words": post_3_words,
        "post_4_words": post_4_words,
        "all_unique_words": day_pool[:10],
        "post_2_new_words": post_2_new,
        "post_4_new_words": post_4_new,
    }


if __name__ == "__main__":
    print("Loading word packs...")
    all_words = load_word_packs_from_js()
    print(f"\nTotal: {len(all_words)} words")

    print("\n--- Session 1 candidate pool ---")
    candidates = get_candidate_words(all_words, session=1, count=30)

    print("\n--- Session 2 candidate pool ---")
    candidates2 = get_candidate_words(all_words, session=2, count=30)

    overlap = set(w["word"] for w in candidates) & set(w["word"] for w in candidates2)
    print(f"\nOverlap between session 1 and 2: {len(overlap)} words (should be 0)")
