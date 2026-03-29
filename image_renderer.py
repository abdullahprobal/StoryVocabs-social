"""Renders HTML templates to PNG images using Playwright."""

import os
import re
from pathlib import Path


def escape_html(text):
    """Escape HTML special chars but preserve bold markers."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert **word** markers to <span class="highlight">
    text = re.sub(r'\*\*(.+?)\*\*', r'<span class="highlight">\1</span>', text)
    return text


def build_words_html(words):
    """Build HTML for vocabulary summary slide."""
    items = []
    for i, w in enumerate(words, 1):
        items.append(f"""
        <div class="word-item">
          <div class="word-row">
            <span class="word">{i}. {w['word']}</span>
            <span class="pronunciation">{w.get('pronunciation', '')}</span>
          </div>
          <div class="meaning">🇧🇩 {w.get('bangla', '')}</div>
          <div class="example">"{w.get('example', '')}"</div>
        </div>""")
    return "\n".join(items)


def build_reel_words_html(words):
    """Build HTML for reel overlay (dark theme)."""
    items = []
    for i, w in enumerate(words, 1):
        items.append(f"""
        <div class="word-card">
          <div class="word-num">শব্দ {i}</div>
          <div class="word">{w['word']}</div>
          <div class="pronunciation">{w.get('pronunciation', '')}</div>
          <div class="meaning">{w.get('bangla', '')}</div>
          <div class="example">"{w.get('example', '')}"</div>
        </div>""")
    return "\n".join(items)


def build_whatsapp_words_html(words):
    """Build compact word list for WhatsApp."""
    items = []
    for w in words:
        items.append(f"""
        <div class="word-item">
          <div class="word-row">
            <span class="word">{w['word']}</span>
            <span class="bangla">{w.get('bangla', '')}</span>
          </div>
        </div>""")
    return "\n".join(items)


def split_story_into_chunks(story, chunk_size=3):
    """Split story sentences into chunks for multiple slides."""
    # Split by Bengali full stop or English period
    sentences = re.split(r'([।.])', story)
    # Rejoin sentences with their delimiters
    joined = []
    for i in range(0, len(sentences) - 1, 2):
        joined.append(sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else ""))
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        joined.append(sentences[-1])
    
    chunks = []
    for i in range(0, len(joined), chunk_size):
        chunk = " ".join(joined[i:i + chunk_size])
        chunks.append(chunk)
    
    # Ensure we have exactly 3 story chunks
    while len(chunks) < 3:
        chunks.append("")
    return chunks[:3]


def render_images(content, output_dir):
    """Main function: render all carousel slides + extras to PNG."""
    from playwright.sync_api import sync_playwright
    
    templates_dir = Path(__file__).parent / "templates"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    date_str = content.get("date", "unknown")
    title = content.get("title", "Untitled")
    words = content.get("words", [])
    story = content.get("story", "")
    category = content.get("category", {})
    exam_note = content.get("exam_note", "")
    
    category_str = f"{category.get('bn', '')} ({category.get('en', '')})"
    word_count = len(words)
    
    # Prepare story chunks
    story_chunks = split_story_into_chunks(story)
    
    # Load templates
    def load_template(name):
        return (templates_dir / name).read_text(encoding="utf-8")
    
    # Build slide data
    slides = []
    
    # Slide 1: Cover
    cover_html = load_template("carousel_cover.html")
    cover_html = cover_html.replace("{{CATEGORY}}", category_str)
    cover_html = cover_html.replace("{{DATE}}", date_str)
    cover_html = cover_html.replace("{{TITLE}}", escape_html(title))
    cover_html = cover_html.replace("{{WORD_COUNT}}", str(word_count))
    slides.append(("slide_1_cover.png", cover_html, (1080, 1080)))
    
    # Slides 2-4: Story
    story_template = load_template("carousel_story.html")
    for idx, chunk in enumerate(story_chunks):
        html = story_template
        html = html.replace("{{SLIDE_NUM}}", str(idx + 2))
        html = html.replace("{{CATEGORY}}", category.get("en", ""))
        html = html.replace("{{STORY_TEXT}}", escape_html(chunk))
        if idx == 0:
            html = html.replace("{{PAGE_HINT}}", "শুরু →")
        elif idx == 1:
            html = html.replace("{{PAGE_HINT}}", "← মাঝে →")
        else:
            html = html.replace("{{PAGE_HINT}}", "← শেষ")
        slides.append((f"slide_{idx + 2}_story.png", html, (1080, 1080)))
    
    # Slide 5: Vocabulary
    vocab_html = load_template("carousel_vocab.html")
    vocab_html = vocab_html.replace("{{WORDS_HTML}}", build_words_html(words))
    vocab_html = vocab_html.replace("{{EXAM_NOTE}}", escape_html(exam_note))
    slides.append(("slide_5_vocab.png", vocab_html, (1080, 1080)))
    
    # Reel overlay
    reel_html = load_template("reel_overlay.html")
    reel_html = reel_html.replace("{{WORD_CARDS}}", build_reel_words_html(words))
    reel_html = reel_html.replace("{{WORD_COUNT}}", str(word_count))
    slides.append(("reel_overlay.png", reel_html, (1080, 1920)))
    
    # WhatsApp forwardable
    wa_html = load_template("whatsapp_forward.html")
    wa_html = wa_html.replace("{{WORDS_HTML}}", build_whatsapp_words_html(words))
    wa_html = wa_html.replace("{{WORD_COUNT}}", str(word_count))
    slides.append(("whatsapp.png", wa_html, (800, 800)))
    
    # Render all slides
    print(f"🎨 Rendering {len(slides)} images...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        for filename, html, size in slides:
            page = browser.new_page(
                viewport={"width": size[0], "height": size[1]},
                device_scale_factor=1,
            )
            page.set_content(html, wait_until="networkidle")
            
            # Write temp HTML for debugging
            temp_html = output_path / f"_temp_{filename}.html"
            temp_html.write_text(html, encoding="utf-8")
            
            # Screenshot the body
            page.screenshot(
                path=str(output_path / filename),
                type="png",
                full_page=False,
            )
            page.close()
            print(f"  ✅ {filename}")
        
        browser.close()
    
    # Clean up temp HTML files
    for f in output_path.glob("_temp_*.html"):
        f.unlink()
    
    print(f"📁 All images saved to: {output_path}")
    return [str(output_path / s[0]) for s in slides]


if __name__ == "__main__":
    import json
    sample_content = {
        "date": "2026-03-30",
        "title": "বাংলাদেশ ব্যাংক নতুন নীতি ঘোষণা করেছে",
        "story": "বাংলাদেশ ব্যাংক **monetary policy** এ বড় পরিবর্তন এনেছে। তারা **inflation** নিয়ন্ত্রণে হার বাড়িয়েছে। এতে করে **loan** নেওয়া আরও ব্যয়বহুল হবে। তবে **analysts** মনে করেন এটা দীর্ঘমেয়াদে অর্থনীতিকে **stabilize** করবে।",
        "words": [
            {"word": "Monetary Policy", "pronunciation": "/ˈmʌn.ɪ.tər.i ˈpɒl.ɪ.si/", "bangla": "মুদ্রানীতি", "example": "The bank updated its monetary policy."},
            {"word": "Inflation", "pronunciation": "/ɪnˈfleɪ.ʃən/", "bangla": "মুদ্রাস্ফীতি", "example": "Inflation rose to 9% this month."},
            {"word": "Stabilize", "pronunciation": "/ˈsteɪ.bə.laɪz/", "bangla": "স্থিতিশীল করা", "example": "The measures will stabilize the economy."},
        ],
        "exam_note": "এই শব্দগুলো BCS, Bank AD, এবং Admission পরীক্ষায় ঘন ঘন আসে",
        "category": {"bn": "অর্থনীতি ও ব্যাংকিং", "en": "Economy & Banking"},
    }
    
    out_dir = Path(__file__).parent / "output" / "sample"
    render_images(sample_content, str(out_dir))
