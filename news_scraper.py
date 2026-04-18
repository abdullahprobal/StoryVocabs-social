"""Fetches diverse Bangladesh news stories. Supports pool caching and session-indexed picking."""

import feedparser
import json
import re
from pathlib import Path
from html import unescape
from datetime import datetime, timedelta


STORY_TRACKER = Path(__file__).parent / "story_usage_tracker.json"
MAX_STORY_USAGE = 2
MIN_GAP_DAYS = 180

# News pool is cached per date to avoid re-scraping across sessions
NEWS_POOL_CACHE_DIR = Path(__file__).parent / "output"


def clean(text):
    text = re.sub(r'<[^>]+>', '', text or "")
    return unescape(text).strip()


def get_schedule_for_day(weekday):
    """Get genre schedule for a specific weekday (0=Mon, 6=Sun)."""
    from config import GENRE_SCHEDULE
    return GENRE_SCHEDULE.get(weekday)


def get_today_schedule():
    """Get today's genre schedule."""
    from config import GENRE_SCHEDULE
    day = datetime.now().weekday()
    schedule = GENRE_SCHEDULE.get(day)
    if schedule is None:
        print("   Wednesday — OFF DAY. No content today.")
        return None
    print(f"   Genre: {schedule['label']}")
    return schedule


def get_alternative_genre():
    """Get a genre from a different day for Topic B variety."""
    from config import GENRE_SCHEDULE
    today = datetime.now().weekday()
    alt_day = (today + 3) % 7
    schedule = GENRE_SCHEDULE.get(alt_day)
    if schedule:
        print(f"   Topic B Genre (alt): {schedule['label']}")
    return schedule


def load_story_tracker():
    if STORY_TRACKER.exists():
        try:
            return json.loads(STORY_TRACKER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_story_tracker(tracker):
    STORY_TRACKER.write_text(json.dumps(tracker, indent=2, ensure_ascii=False), encoding="utf-8")


def story_key(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())[:60]


def is_story_usable(tracker, title):
    key = story_key(title)
    today = datetime.now()
    if key not in tracker:
        return True
    entries = tracker[key]
    year = str(today.year)
    year_count = sum(1 for e in entries if e.get("date", "").startswith(year))
    if year_count >= MAX_STORY_USAGE:
        return False
    for entry in entries:
        try:
            used_date = datetime.strptime(entry["date"], "%Y-%m-%d")
            gap = (today - used_date).days
            if gap < MIN_GAP_DAYS:
                return False
        except Exception:
            continue
    return True


def mark_story_used(tracker, title, date_str):
    key = story_key(title)
    if key not in tracker:
        tracker[key] = []
    tracker[key].append({"date": date_str, "title": title[:100]})
    return tracker


def fetch_rss():
    from config import NEWS_SOURCES
    articles = []
    for url in NEWS_SOURCES:
        try:
            feed = feedparser.parse(url)
            source = url.split("/")[2].replace("www.", "").split(".")[0]
            for entry in feed.entries[:8]:
                title = clean(entry.get("title", ""))
                summary = clean(entry.get("summary", entry.get("description", "")))
                if len(title) > 20:
                    articles.append({
                        "title": title,
                        "summary": summary[:500],
                        "source": source,
                    })
        except Exception:
            continue
    return articles


def fetch_google_news(queries):
    articles = []
    for query in queries:
        try:
            encoded = query.replace(" ", "+")
            url = f"https://news.google.com/rss/search?q={encoded}+when:1d&hl=en-BD&gl=BD&ceid=BD:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = clean(entry.get("title", ""))
                summary = clean(entry.get("summary", ""))
                if len(title) > 20:
                    articles.append({
                        "title": title,
                        "summary": summary[:500],
                        "source": "google_news",
                    })
        except Exception:
            continue
    return articles


def score_article(article, keywords):
    text = (article["title"] + " " + article["summary"]).lower()
    score = 0
    for kw in keywords:
        if kw in text:
            score += 3
    viral = ["record", "billion", "million", "crisis", "breakthrough", "first",
             "historic", "unprecedented", "viral", "win", "defeat", "launch",
             "reform", "protest", "scandal", "arrest", "surge", "collapse",
             "free", "new", "biggest", "warning", "trending",
             "কোটি", "বিলিয়ন", "রেকর্ড", "প্রথমবার"]
    for v in viral:
        if v in text:
            score += 2
    boring = ["opinion", "editorial", "column"]
    for b in boring:
        if b in text:
            score -= 5
    return score


def deduplicate_articles(articles):
    """Remove duplicate articles by title key."""
    seen = set()
    unique = []
    for a in articles:
        key = story_key(a["title"])
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def scrape_news_pool(date_str=None, count=12):
    """Scrape and cache a pool of diverse, high-quality news articles.

    Returns the top `count` scored articles. Caches to disk so repeated
    sessions on the same day don't re-scrape. Cache key is the date string.

    Args:
        date_str: Date string YYYY-MM-DD (defaults to today).
        count: How many articles to return in the pool.

    Returns:
        List of up to `count` article dicts, sorted by score descending.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Check cache first
    cache_dir = NEWS_POOL_CACHE_DIR / date_str
    cache_file = cache_dir / "news_pool.json"

    if cache_file.exists():
        try:
            pool = json.loads(cache_file.read_text(encoding="utf-8"))
            print(f"   News pool: loaded {len(pool)} articles from cache ({date_str})")
            return pool
        except Exception:
            pass

    # Build combined query list from today + alternative genres
    weekday = datetime.now().weekday()
    schedule_a = get_schedule_for_day(weekday)
    alt_day = (weekday + 3) % 7
    schedule_b = get_schedule_for_day(alt_day)
    # Also query a third genre for variety
    alt_day2 = (weekday + 5) % 7
    schedule_c = get_schedule_for_day(alt_day2)

    all_articles = fetch_rss()
    if schedule_a:
        all_articles += fetch_google_news(schedule_a["queries"])
    if schedule_b:
        all_articles += fetch_google_news(schedule_b["queries"])
    if schedule_c:
        all_articles += fetch_google_news(schedule_c["queries"][:2])  # limit queries

    print(f"   Raw articles fetched: {len(all_articles)}")
    unique = deduplicate_articles(all_articles)
    print(f"   After dedup: {len(unique)}")

    tracker = load_story_tracker()
    usable = [a for a in unique if is_story_usable(tracker, a["title"])]
    print(f"   After tracker filter: {len(usable)}")

    if len(usable) < 4:
        print("   Not enough new stories — including already-used articles")
        usable = unique

    # Combine keyword lists for scoring
    all_keywords = []
    for s in [schedule_a, schedule_b, schedule_c]:
        if s:
            all_keywords.extend(s.get("keywords", []))

    scored = sorted(
        [(score_article(a, all_keywords), a) for a in usable],
        key=lambda x: x[0],
        reverse=True
    )

    # Take top `count`, ensuring diversity (no two articles about same topic)
    pool = []
    seen_keys = set()
    for score, article in scored:
        key = story_key(article["title"])
        if key not in seen_keys:
            seen_keys.add(key)
            pool.append(article)
        if len(pool) >= count:
            break

    # Pad if not enough
    if len(pool) < count:
        for _, article in scored:
            if article not in pool:
                pool.append(article)
            if len(pool) >= count:
                break

    print(f"   News pool built: {len(pool)} articles")
    for i, a in enumerate(pool[:12]):
        print(f"   [{i+1}] {a['title'][:70]}")

    # Save cache
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")

    return pool


def scrape_news(session=1, date_str=None):
    """Get 2 diverse news stories for this session's posts.

    Each session gets a unique pair of stories from the pool:
    - Session 1 → pool[0] and pool[3]
    - Session 2 → pool[1] and pool[4]
    - Session 3 → pool[2] and pool[5]
    - Session 4 → pool[6] and pool[7]
    - Session 5+ → wraps around

    Args:
        session: Session number (1-based).
        date_str: Date string YYYY-MM-DD (defaults to today).

    Returns:
        dict with topic_a, topic_b, date, day, genre keys.
    """
    today = datetime.now()
    if date_str is None:
        date_str = today.strftime("%Y-%m-%d")

    weekday = today.weekday()
    schedule_a = get_schedule_for_day(weekday)
    if schedule_a is None:
        print("   Off day, no content.")
        return None

    print(f"   Topic A genre: {schedule_a['label']} | Session {session}")

    # Get or build the news pool
    pool = scrape_news_pool(date_str=date_str)
    if not pool:
        return None

    pool_size = len(pool)

    # Session-indexed story picking: each session gets a unique pair
    # First story index: (session - 1) % half_pool
    # Second story index: first + half_pool (ensure diversity)
    half = max(pool_size // 2, 1)
    first_idx = (session - 1) % half
    second_idx = (first_idx + half) % pool_size

    # Ensure they're different
    if second_idx == first_idx and pool_size > 1:
        second_idx = (first_idx + 1) % pool_size

    topic_a = pool[first_idx]
    topic_b = pool[second_idx]

    # Final safety check: ensure A != B
    if story_key(topic_a["title"]) == story_key(topic_b["title"]):
        for alt in pool:
            if story_key(alt["title"]) != story_key(topic_a["title"]):
                topic_b = alt
                break

    tracker = load_story_tracker()
    for s in [topic_a, topic_b]:
        if s.get("source") != "fallback":
            mark_story_used(tracker, s["title"], date_str)
    save_story_tracker(tracker)

    print(f"   Topic A [{first_idx+1}]: {topic_a['title'][:65]}")
    print(f"   Topic B [{second_idx+1}]: {topic_b['title'][:65]}")

    return {
        "date": date_str,
        "day": today.strftime("%A"),
        "genre": schedule_a["label"],
        "genres": schedule_a["genres"],
        "session": session,
        "topic_a": topic_a,
        "topic_b": topic_b,
        "total_found": pool_size,
    }


if __name__ == "__main__":
    print("Testing scrape_news_pool...")
    pool = scrape_news_pool()
    print(f"\nPool size: {len(pool)}")

    print("\n--- Session 1 ---")
    r1 = scrape_news(session=1)
    if r1:
        print(f"A: {r1['topic_a']['title']}")
        print(f"B: {r1['topic_b']['title']}")

    print("\n--- Session 2 ---")
    r2 = scrape_news(session=2)
    if r2:
        print(f"A: {r2['topic_a']['title']}")
        print(f"B: {r2['topic_b']['title']}")

    print("\n--- Session 3 ---")
    r3 = scrape_news(session=3)
    if r3:
        print(f"A: {r3['topic_a']['title']}")
        print(f"B: {r3['topic_b']['title']}")
