"""Bangladesh news pool for the News Word pillar.

Sources: six BD English RSS feeds + Google News RSS searches for the day's
topic group. Cached per date under output/news/. Story usage is tracked in
state/story_usage_tracker.json (6-month gap, max 2 uses) so the same story
is never retold soon.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from html import unescape

import feedparser

from engine import settings

TRACKER = settings.STATE_DIR / "story_usage_tracker.json"
CACHE_DIR = settings.OUTPUT_DIR / "news"
MAX_STORY_USAGE = 2
MIN_GAP_DAYS = 180

NEWS_SOURCES = settings.NEWS.get("feeds", [])
_LOCALE = settings.NEWS.get("google_news_locale", {"hl": "en", "gl": "US", "ceid": "US:en"})

TOPIC_KEYWORDS = {
    "politics": ["politic", "parliament", "government", "minister", "election", "vote", "democracy", "law", "court",
                 "reform", "cricket", "football", "match", "tournament", "team", "odi", "t20", "test", "history",
                 "heritage", "independence", "geopolitic", "foreign", "diplomat", "border", "india", "china",
                 "united nations", "rohingya", "treaty", "summit"],
    "business": ["technology", "digital", "ai", "internet", "app", "startup", "innovation", "software", "tech",
                 "online", "business", "trade", "economy", "market", "company", "entrepreneur", "investment",
                 "export", "import", "rmg", "garment", "bank", "finance", "stock", "payment", "remittance"],
    "general": ["bangladesh", "dhaka", "student", "university", "education", "exam"],
}

SENSITIVE = ("rape", "murder", "killed", "dead body", "death toll", "suicide", "abuse", "molest",
             "gang", "blast", "bomb", "stabbed", "lynch", "genocide", "massacre", "corpse", "hanged",
             "ধর্ষণ", "হত্যা", "খুন", "লাশ", "আত্মহত্যা")

TOPIC_QUERIES = settings.NEWS.get("queries") or {
    "politics": ["Bangladesh politics", "Bangladesh government reform", "Bangladesh geopolitics India China",
                 "Bangladesh cricket", "Bangladesh election"],
    "business": ["Bangladesh economy", "Bangladesh business trade", "Bangladesh startup technology",
                 "Bangladesh banking finance", "Bangladesh digital payment"],
    "general": ["Bangladesh news today", "Bangladesh education", "Bangladesh Dhaka"],
}


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def story_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())[:60]


# ── tracker ────────────────────────────────────────────────────────────────
def load_tracker() -> dict:
    if TRACKER.exists():
        try:
            return json.loads(TRACKER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_tracker(tracker: dict) -> None:
    TRACKER.write_text(json.dumps(tracker, indent=1, ensure_ascii=False), encoding="utf-8")


def is_story_usable(tracker: dict, title: str, today: datetime | None = None) -> bool:
    uses = tracker.get(story_key(title), [])
    if len(uses) >= MAX_STORY_USAGE:
        return False
    today = today or datetime.now()
    for u in uses:
        try:
            d = datetime.strptime(u["date"], "%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        if (today - d).days < MIN_GAP_DAYS:
            return False
    return True


def mark_story_used(title: str, date_str: str) -> None:
    tracker = load_tracker()
    tracker.setdefault(story_key(title), []).append({"date": date_str, "title": title[:120]})
    save_tracker(tracker)


# ── fetching ───────────────────────────────────────────────────────────────
def fetch_rss(limit_per_feed: int = 10) -> list[dict]:
    out = []
    for url in NEWS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:  # noqa: BLE001
            continue
        source = url.split("/")[2].replace("www.", "").split(".")[0]
        for e in feed.entries[:limit_per_feed]:
            title = clean(e.get("title", ""))
            if len(title) < 20:
                continue
            out.append({
                "title": title,
                "summary": clean(e.get("summary", e.get("description", "")))[:600],
                "source": source,
                "link": e.get("link", ""),
                "published": e.get("published", ""),
            })
    return out


def fetch_google_news(queries: list[str], per_query: int = 4) -> list[dict]:
    out = []
    for q in queries:
        url = (f"https://news.google.com/rss/search?q={q.replace(' ', '+')}+when:2d"
               f"&hl={_LOCALE['hl']}&gl={_LOCALE['gl']}&ceid={_LOCALE['ceid']}")
        try:
            feed = feedparser.parse(url)
        except Exception:  # noqa: BLE001
            continue
        for e in feed.entries[:per_query]:
            title = clean(e.get("title", ""))
            if len(title) < 20:
                continue
            # Google titles end with " - Source"
            source = title.rsplit(" - ", 1)[1] if " - " in title else "google_news"
            out.append({
                "title": title.rsplit(" - ", 1)[0],
                "summary": clean(e.get("summary", ""))[:600],
                "source": source,
                "link": e.get("link", ""),
                "published": e.get("published", ""),
            })
    return out


def score_article(a: dict, keywords: list[str]) -> int:
    text = (a["title"] + " " + a["summary"]).lower()
    score = sum(3 for k in keywords if k in text)
    for v in ("record", "billion", "million", "crisis", "first", "historic", "win", "launch",
              "reform", "protest", "surge", "new", "biggest", "warning", "students", "exam", "university"):
        if v in text:
            score += 2
    for b in ("opinion", "editorial", "column", "obituary", "horoscope", "recipe"):
        if b in text:
            score -= 5
    # A learning brand must not build vocabulary lessons on tragedy or crime.
    for s in SENSITIVE:
        if s in text:
            return -100
    if a.get("source") in ("thedailystar", "dhakatribune", "tbsnews", "bdnews24", "prothomalo", "thefinancialexpress-bd"):
        score += 1
    return score


def dedupe(articles: list[dict]) -> list[dict]:
    seen, out = set(), []
    for a in articles:
        k = story_key(a["title"])
        if k and k not in seen:
            seen.add(k)
            out.append(a)
    return out


def news_pool(date_str: str, topic_group: str = "general", count: int = 12, refresh: bool = False) -> list[dict]:
    """Top `count` fresh, unused, on-topic articles for the date (cached)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{date_str}_{topic_group}.json"
    if cache.exists() and not refresh:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    queries = TOPIC_QUERIES.get(topic_group, TOPIC_QUERIES["general"])
    keywords = TOPIC_KEYWORDS.get(topic_group, TOPIC_KEYWORDS["general"])

    articles = dedupe(fetch_rss() + fetch_google_news(queries))
    tracker = load_tracker()
    usable = [a for a in articles if is_story_usable(tracker, a["title"])] or articles
    scored = sorted(usable, key=lambda a: score_article(a, keywords), reverse=True)
    pool = [a for a in scored if score_article(a, keywords) > -100][:count]
    cache.write_text(json.dumps(pool, indent=1, ensure_ascii=False), encoding="utf-8")
    return pool
