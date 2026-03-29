"""Fetches daily Bangladesh news from RSS feeds and Google News."""

import feedparser
import requests
import json
import random
from datetime import datetime


def fetch_rss_news():
    """Fetch from RSS feeds."""
    from config import NEWS_SOURCES
    
    articles = []
    for url in NEWS_SOURCES:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "source": url.split("/")[2],
                })
        except Exception:
            continue
    return articles


def fetch_google_news():
    """Fetch from Google News RSS for Bangladesh."""
    from config import NEWS_GOOGLE_QUERIES
    
    articles = []
    for query in NEWS_GOOGLE_QUERIES:
        try:
            encoded_q = query.replace(" ", "+")
            url = f"https://news.google.com/rss/search?q={encoded_q}+Bangladesh&hl=en-BD&gl=BD&ceid=BD:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:300],
                    "link": entry.get("link", ""),
                    "source": "Google News",
                })
        except Exception:
            continue
    return articles


def pick_todays_story(all_articles, category_index):
    """Pick the best story for today's category."""
    from config import DAILY_CATEGORIES
    
    category = DAILY_CATEGORIES.get(category_index, DAILY_CATEGORIES[6])
    
    # Filter by category keywords
    category_keywords = {
        0: ["politic", "parliament", "government", "minister", "election", "policy", "law", "court", "শাসন"],
        1: ["bank", "economy", "trade", "budget", "inflation", "export", "import", "gdp", "stock", "currency"],
        2: ["international", "diplomat", "treaty", "foreign", "united nations", "india", "china", "usa"],
        3: ["science", "technology", "digital", "internet", "ai", "satellite", "research", "innovation"],
        4: ["history", "culture", "heritage", "language", "literature", "museum", "tradition"],
        5: ["climate", "environment", "flood", "cyclone", "pollution", "river", "forest", "coast"],
        6: [],  # GK — any topic
    }
    
    keywords = category_keywords.get(category_index, [])
    
    if keywords:
        scored = []
        for article in all_articles:
            text = (article["title"] + " " + article["summary"]).lower()
            score = sum(1 for kw in keywords if kw in text)
            scored.append((score, article))
        scored.sort(key=lambda x: x[0], reverse=True)
        
        if scored[0][0] > 0:
            return scored[0][1], category
    
    # Fallback: random pick
    if all_articles:
        return random.choice(all_articles), category
    
    return None, category


def scrape_news():
    """Main function: scrape and save today's news."""
    today = datetime.now()
    category_index = today.weekday()  # 0=Monday, 6=Sunday
    
    rss_articles = fetch_rss_news()
    google_articles = fetch_google_news()
    all_articles = rss_articles + google_articles
    
    story, category = pick_todays_story(all_articles, category_index)
    
    result = {
        "date": today.strftime("%Y-%m-%d"),
        "day_of_week": today.strftime("%A"),
        "category": category,
        "all_headlines": [a["title"] for a in all_articles[:10]],
        "selected_story": story,
        "total_articles_found": len(all_articles),
    }
    
    print(f"📰 Found {len(all_articles)} articles")
    print(f"📂 Category: {category['bn']} ({category['en']})")
    if story:
        print(f"✅ Selected: {story['title'][:80]}")
    else:
        print("⚠️ No story found — will use fallback topic")
    
    return result


if __name__ == "__main__":
    result = scrape_news()
    print(json.dumps(result, indent=2, ensure_ascii=False))
