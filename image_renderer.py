"""Renders HTML to PNG — 1080×1350 carousel from new JSON contract."""

import re
import base64
import html as html_module
from pathlib import Path
from datetime import datetime
from config import CANVAS


def get_logo_base64():
    logo_path = Path(__file__).parent / "assets" / "logo-app-icon.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    return ""


def esc(text):
    return html_module.escape(text or "")


def wrap_hero(headline):
    """Replace [[word]] with <span class="g">word</span>."""
    return re.sub(r'\[\[(.+?)\]\]', r'<span class="g">\1</span>', esc(headline or ""))


def ruby_markup(paragraph):
    """Replace [[en|bn]] with <ruby> markup."""
    if not paragraph:
        return ""
    escaped = esc(paragraph)
    def ruby_repl(m):
        en, bn = m.group(1), m.group(2)
        return f'<ruby class="vw"><span class="vw-en">{en}</span><rt><b>{bn}</b></rt></ruby>'
    return re.sub(r'\[\[(.+?)\|(.+?)\]\]', ruby_repl, escaped)


def keep_bold(text):
    """Keep <b>…</b> tags, escape everything else."""
    if not text:
        return ""
    escaped = esc(text)
    return escaped.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")


def build_recap_rows(words):
    """Build <li> rows for closing slide recap."""
    rows = []
    for i, w in enumerate(words):
        row = f'<li><span class="n">{i+1}</span><span class="en">{esc(w.get("word", ""))}</span><span class="bn">{esc(w.get("gloss_bn", ""))}</span></li>'
        rows.append(row)
    return "".join(rows)


def fmt_date(date_str):
    """Format YYYY-MM-DD to 'Month D, Year'."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = dt.strftime("%B %d, %Y")
        return formatted.replace(" 0", " ")
    except:
        return date_str


# CTA constants
LOGO_SRC = get_logo_base64()
APP_URL = "storyvocabs.vercel.app"
CTA_STORY = "📖 গল্পে শব্দ শিখতে ডাউনলোড করো"
CTA_VOCAB = "📲 আরও শব্দ শিখতে ডাউনলোড করো"
CTA_CLOSE = "📲 প্রতিদিন এভাবে শিখতে অ্যাপটি ডাউনলোড করো"


def render_post_images(content, output_dir):
    """Render images for a single post using the new 1080×1350 contract."""
    from playwright.sync_api import sync_playwright

    tpl_dir = Path(__file__).parent / "templates"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Clean stale PNGs from previous runs
    for old_png in out.glob("*.png"):
        old_png.unlink()

    def load(name):
        return (tpl_dir / name).read_text(encoding="utf-8")

    # Extract fields from NEW contract
    headline_en = content.get("headline_en", "")
    hero_word = content.get("hero_word", "")
    hero_gloss_bn = content.get("hero_gloss_bn", "")
    story_slides = content.get("story_slides", [])
    words = content.get("words", [])
    word_count = content.get("word_count", len(words))
    category = content.get("category", {})
    date_str = content.get("date", "")

    # Calculate total slides: 1 cover + N story + M vocab (1 per word) + 1 closing
    total_slides = 1 + len(story_slides) + len(words) + 1

    # Cap at 20 slides: drop closing first, then merge story slides
    if total_slides > 20:
        # Drop closing
        total_slides -= 1
        if total_slides > 20:
            # Merge story slides (keep only first)
            story_slides = story_slides[:1]
            total_slides = 1 + len(story_slides) + len(words) + 1

    slides = []

    # ─── SLIDE 1: COVER ─────────────────────────────────────────────────────
    cover = load("cover.html")
    cover = cover.replace("{{LOGO_SRC}}", LOGO_SRC)
    cover = cover.replace("{{SLIDE_NUMBER}}", "1")
    cover = cover.replace("{{TOTAL_SLIDES}}", str(total_slides))
    cover = cover.replace("{{CATEGORY_ICON}}", category.get("icon", "📖"))
    cover = cover.replace("{{CATEGORY}}", category.get("en", ""))
    cover = cover.replace("{{DATE}}", fmt_date(date_str))
    cover = cover.replace("{{HEADLINE_HTML}}", wrap_hero(headline_en))
    cover = cover.replace("{{HERO_WORD}}", esc(hero_word))
    cover = cover.replace("{{HERO_BN}}", esc(hero_gloss_bn))
    cover = cover.replace("{{SWIPE_COUNT}}", str(word_count))
    slides.append(("slide_1_cover.png", cover, CANVAS))

    # ─── SLIDES 2+N: STORY ──────────────────────────────────────────────────
    story_tpl = load("story.html")
    for idx, slide_obj in enumerate(story_slides):
        html = story_tpl
        slide_num = 2 + idx
        section_label = slide_obj.get("section_label", "")
        paragraph = slide_obj.get("paragraph", "")

        html = html.replace("{{SECTION_LABEL}}", esc(section_label))
        html = html.replace("{{SLIDE_NUMBER}}", str(slide_num))
        html = html.replace("{{TOTAL_SLIDES}}", str(total_slides))
        html = html.replace("{{STORY_PARAGRAPH}}", ruby_markup(paragraph))
        html = html.replace("{{CTA_LABEL}}", CTA_STORY)
        html = html.replace("{{APP_URL}}", APP_URL)

        slides.append((f"slide_{slide_num}_story.png", html, (1080, 1350)))

    # ─── SLIDES (N+1)+(M): VOCAB ────────────────────────────────────────────
    vocab_tpl = load("vocab.html")
    start_vocab_idx = 2 + len(story_slides)

    for word_idx, word in enumerate(words):
        html = vocab_tpl
        slide_num = start_vocab_idx + word_idx

        html = html.replace("{{WORD_INDEX}}", str(word_idx + 1))
        html = html.replace("{{WORD_TOTAL}}", str(word_count))
        html = html.replace("{{POS}}", esc(word.get("pos", "")))
        html = html.replace("{{DIFFICULTY}}", esc(word.get("difficulty", "")))
        html = html.replace("{{DIFF_CLASS}}", word.get("difficulty", "").lower())
        html = html.replace("{{WORD}}", esc(word.get("word", "")))
        html = html.replace("{{PHONETIC}}", esc(word.get("phonetic", "")))
        html = html.replace("{{MEANING_BN}}", esc(word.get("meaning_bn", "")))
        html = html.replace("{{MEANING_EN}}", esc(word.get("meaning_en", "")))

        example = word.get("example", "")
        example_html = keep_bold(example) if example else ""
        html = html.replace("{{EXAMPLE_HTML}}", example_html)
        html = html.replace("{{CTA_LABEL}}", CTA_VOCAB)
        html = html.replace("{{APP_URL}}", APP_URL)

        slides.append((f"slide_{slide_num}_vocab_{word_idx+1}.png", html, (1080, 1350)))

    # ─── FINAL SLIDE: CLOSING ───────────────────────────────────────────────
    closing_tpl = load("closing.html")
    closing = closing_tpl
    closing = closing.replace("{{SLIDE_NUMBER}}", str(total_slides))
    closing = closing.replace("{{TOTAL_SLIDES}}", str(total_slides))
    closing = closing.replace("{{WORD_TOTAL}}", str(word_count))
    closing = closing.replace("{{RECAP_ROWS_HTML}}", build_recap_rows(words))
    closing = closing.replace("{{CTA_LABEL}}", CTA_CLOSE)
    closing = closing.replace("{{APP_URL}}", APP_URL)
    slides.append((f"slide_{total_slides}_closing.png", closing, (1080, 1350)))

    # ─── RENDER ─────────────────────────────────────────────────────────────
    print(f"   Rendering {len(slides)} slides (1 cover + {len(story_slides)} story + {len(words)} vocab + 1 closing)")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for filename, html_content, size in slides:
            page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2)
            page.set_content(html_content, wait_until="networkidle")

            # Task 2: Wait for self-fit before screenshot
            try:
                page.wait_for_function("window.__fitDone === true", timeout=5000)
            except Exception as e:
                print(f"   ⚠ fit timeout on {filename}: {e}")

            page.screenshot(path=str(out / filename), type="png")
            page.close()
            print(f"   [OK] {filename}")
        browser.close()

    print(f"   Saved to: {out}")
    return [str(out / s[0]) for s in slides]


def render_images(content, output_dir):
    return render_post_images(content, output_dir)
