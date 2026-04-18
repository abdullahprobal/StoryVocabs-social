"""Renders HTML to PNG — smart slide count, dynamic font size, sentence-aware splits,
no thin slides, logo on every slide, HD.
"""

import re
import base64
import html as html_module
from pathlib import Path


# ─── Word count → font-size tiers ─────────────────────────────────────────────
# Designed for Instagram mobile: 1080px canvas → ~280px render width on phone
# Each tier ensures body text reads cleanly without zooming
FONT_TIERS = [
    # (max_total_words, story_px, hook_px, line_height, font_family)
    (40,  "38px", "30px", "1.85", "'Inter','Noto Sans Bengali',sans-serif"),
    (70,  "34px", "27px", "1.80", "'Inter','Noto Sans Bengali',sans-serif"),
    (110, "30px", "25px", "1.75", "'Inter','Noto Sans Bengali',sans-serif"),
    (999, "26px", "22px", "1.70", "'Inter','Noto Sans Bengali',sans-serif"),
]

# Bangla story needs Noto Sans Bengali as dominant font
BANGLA_FONT_FAMILY = "'Noto Sans Bengali','Inter',sans-serif"


def get_font_vars(hook_text, story_text, is_bangla=False):
    """Return CSS variable string for :root{} injection based on content length."""
    total_words = len((hook_text + " " + story_text).split())
    for max_words, story_px, hook_px, lh, family in FONT_TIERS:
        if total_words <= max_words:
            if is_bangla:
                family = BANGLA_FONT_FAMILY
            return (
                f"--story-font-size:{story_px};"
                f"--hook-font-size:{hook_px};"
                f"--story-line-height:{lh};"
                f"--story-font-family:{family}"
            )
    return "--story-font-size:26px;--hook-font-size:22px;--story-line-height:1.70"


def get_logo_base64():
    logo_path = Path(__file__).parent / "static" / "logo-app-icon.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    return ""


def esc(text):
    return html_module.escape(text or "")


def render_bold(text):
    """Convert **word** (Bangla) markers to styled HTML spans."""
    if not text:
        return ""
    t = esc(text)
    t = re.sub(r'\*\*(.+?)\*\*', r'<span class="vw">\1</span>', t)
    t = re.sub(r'\(([^\)]*[\u0980-\u09FF][^\)]*)\)', r' <span class="bn">(\1)</span>', t)
    return t


def truncate_bangla(text, max_words=6):
    if not text:
        return text
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + "..."


def truncate_meaning(text, max_words=14):
    if not text:
        return text
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + "..."


def build_word_card(word, index):
    pos = word.get("partOfSpeech", word.get("part_of_speech", word.get("pos", "")))
    pos_html = f'<span class="pos-tag">{esc(pos)}</span>' if pos else ""
    synonym = word.get("synonym", "")
    syn_html = f'<span class="synonym"> · Syn: {esc(synonym)}</span>' if synonym else ""
    bangla = truncate_bangla(word.get("bangla", ""), max_words=6)
    meaning = truncate_meaning(word.get("meaning", ""), max_words=14)
    sentence = word.get("sentence", "")
    sentence_html = f'<div class="example">"{esc(sentence)}"</div>' if sentence and sentence.strip() else ""
    return f"""<div class="word-card">
      <div class="word-num">{index}</div>
      <div class="word-info">
        <div class="word-top">
          <span class="word">{esc(word.get('word', ''))}</span>
          {pos_html}
        </div>
        <div class="bangla">🇧🇩 {esc(bangla)}{syn_html}</div>
        <div class="meaning-text">{esc(meaning)}</div>
        {sentence_html}
      </div>
    </div>"""


def get_cat_icon(cat_en):
    icons = {
        "Politics & Governance": "🏛️", "Economy & Banking": "💰",
        "Sports": "🏏", "Science & Technology": "🔬",
        "Environment": "🌿", "Society": "👥",
    }
    return icons.get(cat_en, "📖")


def split_at_sentence(text, target_chars):
    """Split at nearest sentence boundary after target_chars."""
    if len(text) <= target_chars:
        return [text, ""]
    search_end = min(len(text), target_chars + 300)
    for i in range(target_chars, search_end):
        if text[i] in '.!?' and (i + 1 >= len(text) or text[i + 1] == ' '):
            p1, p2 = text[:i + 1].strip(), text[i + 1:].strip()
            if p1 and p2:
                return [p1, p2]
    for i in range(target_chars, max(0, target_chars - 200), -1):
        if text[i] in '.!?' and (i + 1 >= len(text) or text[i + 1] == ' '):
            p1, p2 = text[:i + 1].strip(), text[i + 1:].strip()
            if p1 and p2:
                return [p1, p2]
    words = text.split()
    half = len(words) // 2
    return [" ".join(words[:half]), " ".join(words[half:])]


MIN_CHUNK_WORDS = 35  # Any chunk with fewer words gets merged back


def split_content_smart(full_story, num_slides_requested):
    """
    Split story into up to num_slides_requested chunks, but merge any chunk
    with < MIN_CHUNK_WORDS back into the previous one, reducing slide count.
    Returns (chunks_list, actual_slide_count).
    """
    if num_slides_requested == 1:
        return [full_story], 1

    if num_slides_requested == 2:
        mid = len(full_story) // 2
        parts = split_at_sentence(full_story, mid)
        if not parts[1] or len(parts[1].split()) < MIN_CHUNK_WORDS:
            # Second chunk too thin — collapse to 1 slide
            return [full_story], 1
        return parts, 2

    # 3 slides
    third = len(full_story) // 3
    p1, remainder = split_at_sentence(full_story, third)
    if remainder:
        p2, p3 = split_at_sentence(remainder, len(remainder) // 2)
    else:
        p2, p3 = "", ""

    chunks = [c for c in [p1, p2, p3] if c.strip()]

    # Merge any thin chunk into previous
    merged = []
    for chunk in chunks:
        if len(chunk.split()) < MIN_CHUNK_WORDS and merged:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)

    return merged, len(merged)


def render_post_images(content, output_dir):
    """Render images for a single post."""
    from playwright.sync_api import sync_playwright

    tpl_dir = Path(__file__).parent / "templates"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Clean stale PNGs from previous runs
    for old_png in out.glob("*.png"):
        old_png.unlink()

    def load(name):
        return (tpl_dir / name).read_text(encoding="utf-8")

    words = content.get("words", [])
    hook_text = content.get("hook_line", "")
    full_story = content.get("full_story", "")
    fun_fact = content.get("fun_fact", "")
    debate_q = content.get("debate_question", "")
    category = content.get("category", {})
    cat_en = category.get("en", "General")
    cat_bn = category.get("bn", "সাধারণ জ্ঞান")
    cat_icon = get_cat_icon(cat_en)
    date_str = content.get("date", "")
    word_count = len(words)
    style = content.get("style", "short")
    post_label = content.get("post_label", "")

    # Detect if story is Bangla-dominant (for font selection)
    bangla_char_count = sum(1 for c in full_story if '\u0980' <= c <= '\u09FF')
    is_bangla_story = bangla_char_count > len(full_story) * 0.25

    logo_src = get_logo_base64()

    # ── Calculate requested slide count ─────────────
    hook_chars = len(hook_text)
    story_chars = len(full_story)
    debate_chars = len(debate_q)
    total_content_chars = hook_chars + story_chars + debate_chars

    if style == "short":
        requested_story_slides = 1 if total_content_chars <= 700 else 2
    else:
        if total_content_chars <= 900:
            requested_story_slides = 2
        else:
            requested_story_slides = 3

    # ── Smart split with thin-slide prevention ───────
    chunks, num_story_slides = split_content_smart(full_story, requested_story_slides)

    # ── Vocab slides (3 words per slide max) ─────────
    max_words_per_slide = 3
    num_vocab_slides = (len(words) + max_words_per_slide - 1) // max_words_per_slide

    total_slides = 1 + num_story_slides + num_vocab_slides

    slides = []

    # ─── COVER ──────────────────────────────────────
    cover = load("carousel_cover.html")
    cover = cover.replace("{{LOGO_SRC}}", logo_src)
    cover = cover.replace("{{CATEGORY_ICON}}", cat_icon)
    cover = cover.replace("{{CATEGORY}}", cat_bn)
    cover = cover.replace("{{DATE}}", date_str)
    cover = cover.replace("{{TITLE}}", render_bold(hook_text))
    cover = cover.replace("{{WORD_COUNT}}", str(word_count))
    cover = cover.replace("{{POST_LABEL}}", post_label)
    slides.append(("slide_1_cover.png", cover, (1080, 1080)))

    # ─── STORY SLIDES ───────────────────────────────
    story_tpl = load("carousel_story.html")
    section_labels = ["শুরু — THE HOOK", "বিশ্লেষণ — DEEP DIVE", "প্রভাব — IMPACT"]

    # Assign hook to first slide, debate to last slide, fun_fact to slide 2 if exists
    for idx, chunk in enumerate(chunks):
        html = story_tpl

        # Dynamic font size based on this slide's content density
        slide_hook = hook_text if idx == 0 else ""
        font_vars = get_font_vars(slide_hook, chunk, is_bangla=is_bangla_story)
        html = html.replace("{{FONT_VARS}}", font_vars)

        html = html.replace("{{LOGO_SRC}}", logo_src)
        html = html.replace("{{SECTION_LABEL}}", section_labels[idx] if idx < len(section_labels) else f"অংশ {idx+1}")
        html = html.replace("{{SLIDE_NUM}}", str(idx + 2))
        html = html.replace("{{TOTAL_SLIDES}}", str(total_slides))

        # Hook card (first slide only)
        if idx == 0 and slide_hook:
            html = html.replace("{{HOOK_HTML}}", f'<div class="hook-box">{render_bold(slide_hook)}</div>')
        else:
            html = html.replace("{{HOOK_HTML}}", "")

        # Story paragraph
        html = html.replace("{{STORY_HTML}}", f'<div class="story-para">{render_bold(chunk)}</div>' if chunk else "")

        # Extra box: fun-fact on slide 2, debate on last slide
        extra = ""
        if idx == 1 and fun_fact and num_story_slides >= 2:
            extra = f'<div class="extra-box fact">💡 {esc(fun_fact)}</div>'
        elif idx == num_story_slides - 1 and debate_q:
            extra = f'<div class="extra-box debate">💬 {render_bold(debate_q)}</div>'
        html = html.replace("{{EXTRA_HTML}}", extra)

        slides.append((f"slide_{idx+2}_story.png", html, (1080, 1080)))

    # ─── VOCAB SLIDES ───────────────────────────────
    vocab_tpl = load("carousel_vocab.html")
    for slide_idx in range(num_vocab_slides):
        start = slide_idx * max_words_per_slide
        batch = words[start:start + max_words_per_slide]

        vocab_html = vocab_tpl
        vocab_html = vocab_html.replace("{{LOGO_SRC}}", logo_src)
        vocab_html = vocab_html.replace("{{WORDS_HTML}}", "".join(build_word_card(w, start + i + 1) for i, w in enumerate(batch)))
        vocab_html = vocab_html.replace("{{WORD_COUNT}}", str(word_count))
        exam_note = f"এই শব্দগুলো BCS, Bank, Admission, IELTS পরীক্ষায় আসে — {post_label}"
        vocab_html = vocab_html.replace("{{EXAM_NOTE}}", esc(exam_note))
        vocab_html = vocab_html.replace("{{PAGE_DOTS}}", "")

        vocab_slide_num = len(slides) + 1
        slide_name = f"slide_{vocab_slide_num}_vocab.png" if num_vocab_slides == 1 else f"slide_{vocab_slide_num}_vocab_{slide_idx+1}.png"
        slides.append((slide_name, vocab_html, (1080, 1080)))

    # ─── RENDER ─────────────────────────────────────
    print(f"   Rendering {len(slides)} slides (1 cover + {num_story_slides} story + {num_vocab_slides} vocab) | {'Bangla' if is_bangla_story else 'English'} story")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for filename, html_content, size in slides:
            page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2)
            page.set_content(html_content, wait_until="networkidle")
            page.screenshot(path=str(out / filename), type="png")
            page.close()
            print(f"   ✓ {filename}")
        browser.close()

    print(f"   Saved to: {out}")
    return [str(out / s[0]) for s in slides]


def render_images(content, output_dir):
    return render_post_images(content, output_dir)
