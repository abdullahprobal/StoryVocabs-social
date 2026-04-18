"""
StoryVocabs Social Media Generator v4 — Session-Based, Quality-First

Pipeline: Candidate Words → News Pool → Word-Topic Alignment → 4 AI Posts → Quality Check → HD Images

New in v4:
  - --session N     : Run a different session for the same date (unique words + news)
  - --date YYYY-MM-DD: Generate for a specific date (uses today's scraped news)
  - Topic-first word alignment: words chosen AFTER news topics are known
  - Story angle rotation: each session writes from a different angle
  - Quality threshold raised to 7.0

Usage:
    python generate.py                              # Session 1 for today
    python generate.py --session 2                  # Session 2 for today
    python generate.py --session 3                  # Session 3 for today
    python generate.py --date 2026-05-01            # Session 1 for future date
    python generate.py --date 2026-05-01 --session 2  # Session 2 for future date
    python generate.py --story-only                 # Skip image rendering
    python generate.py --manual "headline"          # Custom headline
    python generate.py --post 1                     # Generate only Post 1
"""

import sys
import os
import re
import json
import random
import webbrowser
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def parse_args():
    """Parse command line arguments."""
    args = {
        "story_only": "--story-only" in sys.argv,
        "session": 1,
        "date": None,
        "single_post": None,
        "manual_headline": None,
    }

    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        if idx + 1 < len(sys.argv):
            try:
                args["session"] = int(sys.argv[idx + 1])
            except ValueError:
                pass

    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            args["date"] = sys.argv[idx + 1]

    if "--post" in sys.argv:
        idx = sys.argv.index("--post")
        if idx + 1 < len(sys.argv):
            try:
                args["single_post"] = int(sys.argv[idx + 1])
            except ValueError:
                pass

    if "--manual" in sys.argv:
        idx = sys.argv.index("--manual")
        if idx + 1 < len(sys.argv):
            args["manual_headline"] = " ".join(sys.argv[idx + 1:])

    return args


def main():
    args = parse_args()
    session = args["session"]
    date_override = args["date"]
    story_only = args["story_only"]
    single_post = args["single_post"]
    manual_headline = args["manual_headline"]

    print("=" * 60)
    print("  StoryVocabs Social Media Generator v4")
    print(f"  Session {session} — " + datetime.now().strftime("%A, %B %d, %Y"))
    print("=" * 60)
    print()

    # Check API keys
    from config import OPENROUTER_API_KEY, GROQ_API_KEYS
    if not OPENROUTER_API_KEY and not GROQ_API_KEYS:
        print("ERROR: No API key set in .env (need OPENROUTER_API_KEY or GROQ_API_KEYS)")
        sys.exit(1)

    today = datetime.now()
    # Use overridden date for output dir, but always scrape today's news
    if date_override:
        try:
            datetime.strptime(date_override, "%Y-%m-%d")
            date_str = date_override
        except ValueError:
            print(f"ERROR: Invalid date format '{date_override}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        date_str = today.strftime("%Y-%m-%d")

    output_dir = Path(__file__).parent / "output" / date_str / f"session_{session}"

    # ─── STEP 1: Load Word Packs ──────────────────────────────────
    print(f"Step 1/5: Loading word packs for Session {session}...")
    from word_pack_manager import load_word_packs_from_js, get_candidate_words

    all_words = load_word_packs_from_js()
    if not all_words:
        print("ERROR: No words loaded from word packs!")
        sys.exit(1)

    candidates = get_candidate_words(all_words, session=session, count=30)
    print()

    # ─── STEP 2: Fetch News Stories ───────────────────────────────
    print(f"Step 2/5: Fetching news stories for Session {session}...")
    from news_scraper import scrape_news

    if manual_headline:
        news_data = {
            "date": date_str,
            "day": today.strftime("%A"),
            "topic_a": {
                "title": manual_headline,
                "summary": manual_headline,
                "source": "manual",
            },
            "topic_b": {
                "title": "Another Topic Today",
                "summary": "Today's vocabulary learning continues with a different perspective.",
                "source": "fallback",
            },
        }
        print(f"   Topic A (Manual): {manual_headline[:60]}")
    else:
        news_data = scrape_news(session=session, date_str=date_str)

    if not news_data:
        print("ERROR: No news data available.")
        sys.exit(1)
    print()

    news_stories = [news_data["topic_a"], news_data["topic_b"]]

    # ─── STEP 3: Word-Topic Alignment ─────────────────────────────
    print(f"Step 3/5: Aligning words to topics (Session {session})...")
    from story_writer import select_words_for_session, positional_word_sets_fallback

    word_sets = select_words_for_session(
        candidates,
        topic_a=news_stories[0],
        topic_b=news_stories[1],
        session=session,
    )

    if not word_sets:
        print("   Alignment failed — trying with expanded candidate pool...")
        # Try again with extra words from a second slice
        from word_pack_manager import get_candidate_words as gcw
        extra_candidates = gcw(all_words, session=session + 10, count=30)
        combined = candidates + extra_candidates
        word_sets = select_words_for_session(combined, news_stories[0], news_stories[1], session)

    if not word_sets:
        print("   Using positional fallback for word sets")
        word_sets = positional_word_sets_fallback(candidates)

    if not word_sets:
        print("ERROR: Could not build word sets!")
        sys.exit(1)
    print()

    # ─── STEP 4: Generate All 4 Posts ─────────────────────────────
    print(f"Step 4/5: Writing 4 posts (Session {session}, quality threshold 7.0)...")
    from story_writer import generate_all_posts

    all_posts = generate_all_posts(word_sets, news_stories, date_str, session=session)

    # Save all content
    output_dir.mkdir(parents=True, exist_ok=True)

    for post_key, post_content in all_posts.items():
        post_num = post_key.replace("post_", "")
        content_path = output_dir / f"post_{post_num}_content.json"
        content_path.write_text(
            json.dumps(post_content, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"   Saved: {content_path}")

    # Save combined
    combined_path = output_dir / "content.json"
    combined_path.write_text(
        json.dumps(all_posts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"   Saved combined: {combined_path}")
    print()

    # ─── STEP 5a: Render HD Images ────────────────────────────────
    if not story_only:
        print("Step 5a/5: Rendering HD images for all 4 posts...")
        from image_renderer import render_post_images
        for post_key, post_content in all_posts.items():
            post_num = post_key.replace("post_", "")
            post_dir = output_dir / f"post_{post_num}"
            post_dir.mkdir(parents=True, exist_ok=True)
            image_paths = render_post_images(post_content, str(post_dir))
            print(f"   Post {post_num}: {len(image_paths)} slides")
        print()
    else:
        print("Step 5a/5: Skipping HD image rendering (--story-only mode)")
        print()

    # ─── STEP 5b: Build Captions ──────────────────────────────────
    print("Step 5b/5: Building captions for all 4 posts...")
    from config import get_caption, HASHTAG_POOL

    reference_date = datetime(2026, 3, 29)
    day_number = (today - reference_date).days

    for post_key, post_content in all_posts.items():
        post_num = post_key.replace("post_", "")
        style = post_content.get("style", "short")

        words = post_content.get("words", [])
        category = post_content.get("category", {})
        hook = post_content.get("hook_line", "")
        clean_hook = re.sub(r'\*\*(.+?)\*\*', r'\1', hook) if hook else ""

        cat_icons = {
            "Politics & Governance": "🏛️", "Economy & Banking": "💰",
            "Sports": "🏏", "Science & Technology": "🔬",
            "Environment": "🌿", "Society": "👥",
            "General Knowledge": "📚",
        }
        icon = cat_icons.get(category.get("en", ""), "📖")
        hashtags = " ".join(random.sample(HASHTAG_POOL, min(12, len(HASHTAG_POOL))))

        post_int = int(post_num)
        if post_int == 1:
            revise_count, new_count = 0, 3
        elif post_int == 2:
            revise_count, new_count = 3, 2
        elif post_int == 3:
            revise_count, new_count = 0, 3
        elif post_int == 4:
            revise_count, new_count = 3, 2
        else:
            revise_count, new_count = 0, len(words)

        caption = get_caption(
            style=style,
            word_count=len(words),
            title=clean_hook,
            category_icon=icon,
            category_bn=category.get("bn", ""),
            hashtags=hashtags,
            revise_count=revise_count,
            new_count=new_count,
            post_number=post_int,
            session_number=session,
            day_number=day_number
        )

        caption_path = output_dir / f"post_{post_num}_caption.txt"
        caption_path.write_text(caption, encoding="utf-8")
        print(f"   Post {post_num} caption: {caption_path}")
    print()

    # ─── DONE ─────────────────────────────────────────────────────
    _print_summary(all_posts, output_dir, session)

    # Copy first post caption to clipboard and open Meta Business Suite
    try:
        import subprocess
        first_caption = (output_dir / "post_1_caption.txt").read_text(encoding="utf-8")
        if sys.platform == "win32":
            ps_cmd = [
                "powershell", "-Command",
                f"Set-Clipboard -Value '{first_caption.replace(chr(39), chr(39)+chr(39))}'"
            ]
            subprocess.run(ps_cmd, check=True)
    except Exception:
        pass

    print("Post 1 caption copied to clipboard!")
    print("Opening Meta Business Suite...")
    webbrowser.open("https://business.facebook.com/latest/home")
    print()
    print("Schedule Posts:")
    print("  Post 1 — 8:00 AM  (Quick Bite)")
    print("  Post 2 — 12:00 PM (Deep Dive)")
    print("  Post 3 — 4:00 PM  (Quick Bite)")
    print("  Post 4 — 8:00 PM  (Deep Dive)")


def _print_summary(all_posts, output_dir, session):
    print("=" * 60)
    print(f"  ALL 4 POSTS GENERATED! (Session {session})")
    print("=" * 60)
    print()
    print(f"Output: {output_dir}")
    print()

    needs_review_posts = []
    for post_key, post_content in all_posts.items():
        post_num = post_key.replace("post_", "")
        post_dir = output_dir / f"post_{post_num}"
        score = post_content.get("quality_score", 0)
        nr = post_content.get("needs_review", False)
        flag = " ⚠ NEEDS REVIEW" if nr else " ✓"
        print(f"  ┌─ Post {post_num}: {post_content.get('post_label', '')}")
        print(f"  │  Words: {post_content.get('word_count', 0)} | Score: {score}/10{flag}")
        print(f"  │  Style: {post_content.get('style', 'short')} | Angle: Session {session}")
        if post_dir.exists():
            for f in sorted(post_dir.iterdir()):
                size = f.stat().st_size
                size_str = f"{size/1024:.0f} KB" if size > 1024 else f"{size} B"
                print(f"  │  {f.name} ({size_str})")
        print(f"  └─ Caption: post_{post_num}_caption.txt")
        print()
        if nr:
            needs_review_posts.append(post_num)

    if needs_review_posts:
        print(f"  ⚠ Posts needing review: {', '.join(needs_review_posts)}")
        print("    Check 'needs_review' flag in content JSON and consider regenerating.")
        print()


if __name__ == "__main__":
    main()
