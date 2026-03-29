"""
StoryVocabs Social Media Automation — Master Script

Usage:
    python generate.py              # Full pipeline: news → story → images
    python generate.py --story-only # Just generate story (skip images)
    python generate.py --manual "headline"  # Use your own headline

Output: output/YYYY-MM-DD/ folder with all assets ready to post.
"""

import sys
import os
import json
import webbrowser
from pathlib import Path
from datetime import datetime


def main():
    print("=" * 60)
    print("  🚀 StoryVocabs Social Media Generator")
    print("  📅 " + datetime.now().strftime("%A, %B %d, %Y"))
    print("=" * 60)
    print()
    
    # Check .env
    from config import GROQ_API_KEY
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        print("❌ GROQ_API_KEY not set!")
        print("   1. Copy your key from the app's .env file")
        print("   2. Paste it in StoryVocabs-social/.env")
        print()
        print("   Get a free key at: https://console.groq.com/keys")
        sys.exit(1)
    
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    output_dir = Path(__file__).parent / "output" / date_str
    
    story_only = "--story-only" in sys.argv
    manual_headline = None
    
    if "--manual" in sys.argv:
        idx = sys.argv.index("--manual")
        if idx + 1 < len(sys.argv):
            manual_headline = " ".join(sys.argv[idx + 1:])
    
    # ─── STEP 1: Fetch News ────────────────────────────────
    print("📰 Step 1/4: Fetching today's news...")
    print()
    
    from news_scraper import scrape_news
    
    if manual_headline:
        news_data = {
            "date": date_str,
            "day_of_week": today.strftime("%A"),
            "category": {"bn": "হস্তচালিত", "en": "Manual Entry"},
            "selected_story": {
                "title": manual_headline,
                "summary": manual_headline,
                "link": "",
                "source": "Manual",
            },
            "all_headlines": [manual_headline],
        }
        print(f"📝 Using manual headline: {manual_headline[:60]}")
    else:
        news_data = scrape_news()
    
    print()
    
    # ─── STEP 2: Generate Story with AI ────────────────────
    print("🤖 Step 2/4: Generating story + vocabulary with Groq AI...")
    print()
    
    from story_writer import generate_content
    content = generate_content(news_data)
    
    # Save content JSON
    output_dir.mkdir(parents=True, exist_ok=True)
    content_path = output_dir / "content.json"
    content_path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Content saved: {content_path}")
    print()
    
    if story_only:
        print("✅ Story-only mode. Content saved. Skipping image generation.")
        print(f"📂 Output: {output_dir}")
        return
    
    # ─── STEP 3: Render Images ─────────────────────────────
    print("🎨 Step 3/4: Rendering social media images...")
    print()
    
    from image_renderer import render_images
    image_paths = render_images(content, str(output_dir))
    
    print()
    
    # ─── STEP 4: Generate Caption ──────────────────────────
    print("📝 Step 4/4: Building caption + hashtags...")
    print()
    
    from config import CAPTION_TEMPLATE, HASHTAG_POOL, DAILY_CATEGORIES
    import random
    
    category = content.get("category", DAILY_CATEGORIES[6])
    words = content.get("words", [])
    title = content.get("title", "")
    
    hashtags = " ".join(random.sample(HASHTAG_POOL, min(12, len(HASHTAG_POOL))))
    
    category_icons = {
        "Politics & Governance": "🏛️",
        "Economy & Banking": "💰",
        "International Relations": "🌍",
        "Science & Technology": "🔬",
        "History & Culture": "📚",
        "Environment & Geography": "🌿",
        "General Knowledge": "🏆",
    }
    icon = category_icons.get(category.get("en", ""), "📖")
    
    caption = CAPTION_TEMPLATE.format(
        tagline="খবর পড়ো, শব্দ শেখো, পরীক্ষায় জেতো 📖",
        title=title,
        category_icon=icon,
        category_bn=category.get("bn", ""),
        word_count=len(words),
        hashtags=hashtags,
    )
    
    caption_path = output_dir / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")
    print(f"💾 Caption saved: {caption_path}")
    print()
    
    # ─── DONE ──────────────────────────────────────────────
    print("=" * 60)
    print("  ✅ ALL DONE!")
    print("=" * 60)
    print()
    print(f"📂 Output folder: {output_dir}")
    print()
    print("📋 Files generated:")
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size
        if size > 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        print(f"   📄 {f.name} ({size_str})")
    print()
    
    # ─── Auto-open Meta Business Suite ─────────────────────
    print("🌐 Opening Meta Business Suite in browser...")
    print("📋 Caption copied to clipboard!")
    
    # Copy caption to clipboard (cross-platform)
    try:
        import subprocess
        if sys.platform == "win32":
            subprocess.run(["clip"], input=caption.encode("utf-8"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=caption.encode("utf-8"), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=caption.encode("utf-8"), check=True)
    except Exception:
        print("⚠️ Could not copy to clipboard. Copy from caption.txt manually.")
    
    # Open Meta Business Suite
    webbrowser.open("https://business.facebook.com/latest/home")
    
    print()
    print("👉 NEXT STEPS:")
    print("   1. Meta Business Suite is now open in your browser")
    print("   2. Click 'Create Post'")
    print("   3. Paste caption (already in clipboard)")
    print("   4. Upload slides 1-5 from the output folder")
    print("   5. Schedule or publish!")
    print()
    print("   ⏱️ Total time: ~30 seconds")
    print()


if __name__ == "__main__":
    main()
