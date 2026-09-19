"""HTML → PNG renderer for every pillar (Playwright/Chromium).

Design system lives in BASE_CSS below and the templates in render/templates/.
Fonts and the logo are inlined as data URIs so rendering is identical on the
owner's PC and in GitHub Actions (no CDN, no network).

Public API
    render_story_post(post: StoryPost, out_dir) -> list[str]      cover + story + vocab + recap
    render_quiz(post: QuizPost, out_dir) -> list[str]
    render_confusables(post: ConfusablesPost, out_dir) -> list[str]
    render_in_app(post: InAppPost, out_dir) -> list[str]
    render_offer(post: OfferPost, out_dir) -> list[str]
    render_story_card(cover_html_ctx, out_dir) -> str            1080x1920 for FB/IG Stories
"""
from __future__ import annotations

import base64
import html as html_mod
import json
import re
from datetime import datetime
from pathlib import Path

from engine import settings
from engine.contracts import ConfusablesPost, InAppPost, OfferPost, QuizPost, StoryPost, Word

TPL = settings.TEMPLATE_DIR
ASSETS = settings.ASSET_DIR
FONT_DIR = ASSETS / "fonts"


def esc(s: str) -> str:
    return html_mod.escape(s or "", quote=False)


# ── assets ─────────────────────────────────────────────────────────────────
def _b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


_FONT_CSS: str | None = None


def font_css() -> str:
    global _FONT_CSS
    if _FONT_CSS is None:
        idx = json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))
        rules = []
        for f in idx:
            src = _b64(FONT_DIR / f["file"], "font/woff2")
            ur = f"unicode-range:{f['unicode_range']};" if f.get("unicode_range") else ""
            rules.append(f"@font-face{{font-family:'{f['family']}';font-style:{f['style']};font-weight:{f['weight']};"
                         f"font-display:block;src:url({src}) format('woff2');{ur}}}")
        _FONT_CSS = "\n".join(rules)
    return _FONT_CSS


_LOGO: str | None = None


def logo_src() -> str:
    global _LOGO
    if _LOGO is None:
        logo = settings.LOGO_FILE if settings.LOGO_FILE.exists() else ASSETS / "logo-icon-512.png"
        _LOGO = _b64(logo, "image/png")
    return _LOGO


def fmt_date(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return date_str


# ── design system ──────────────────────────────────────────────────────────
BASE_CSS = """
:root{
  --paper:{{C_PAPER}};--surface:#ffffff;--surface-2:#f1f5f9;--line:#e2e8f0;
  --ink:{{C_INK}};--ink-2:#334155;--muted:#64748b;
  --accent:{{C_ACCENT}};--accent-deep:{{C_ACCENT_DEEP}};--accent-2:{{C_ACCENT_2}};--tint:#eff6ff;--tint-2:#dbeafe;
  --marker:{{C_MARKER}};--marker-ink:#4A3A00;--ok:#15803d;--ok-tint:#dcfce7;--warn:#b45309;--warn-tint:#fef3c7;
  --bn:'Hind Siliguri','Noto Sans Bengali',sans-serif;
  --bn-display:'Tiro Bangla','Hind Siliguri',serif;
  --en:'DM Sans','Hind Siliguri',system-ui,sans-serif;
  --en-display:'Instrument Serif',Georgia,serif;
  --emoji:'Segoe UI Emoji','Noto Color Emoji','Apple Color Emoji',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:{{H}}px;overflow:hidden;background:var(--paper);color:var(--ink);font-family:var(--bn);-webkit-font-smoothing:antialiased}
.canvas{position:relative;width:1080px;height:{{H}}px;overflow:hidden;background:
  radial-gradient(900px 520px at 85% -10%, rgba(37,99,235,.14), transparent 60%),
  radial-gradient(700px 420px at -10% 110%, rgba(124,58,237,.10), transparent 60%),
  var(--paper);}
.canvas:before{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(15,23,42,.055) 1.4px, transparent 1.4px);background-size:28px 28px;opacity:.9;pointer-events:none}
.emoji{font-family:var(--emoji)}
/* header */
.hdr{position:absolute;left:56px;right:56px;top:52px;height:76px;display:flex;align-items:center;justify-content:space-between}
.lockup{display:flex;align-items:center;gap:16px}
.lockup img{width:64px;height:64px;border-radius:14px;box-shadow:0 6px 18px rgba(37,99,235,.28)}
.lockup .wm{font-family:var(--en);font-weight:700;font-size:38px;letter-spacing:-.02em;line-height:1}
.lockup .wm b{color:var(--accent);font-weight:700}
.pill{display:inline-flex;align-items:center;gap:10px;height:52px;padding:0 22px;border-radius:999px;background:var(--surface);border:2px solid var(--line);font-family:var(--en);font-weight:700;font-size:24px;color:var(--ink-2);letter-spacing:.02em}
.pill.blue{background:var(--tint);border-color:var(--tint-2);color:var(--accent-deep)}
/* footer */
.ftr{position:absolute;left:0;right:0;bottom:0;height:112px;background:linear-gradient(90deg,var(--accent) 0%,var(--accent-2) 100%);color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 56px}
.ftr .url{font-family:var(--en);font-weight:700;font-size:31px;letter-spacing:-.01em}
.ftr .cta{font-family:var(--bn);font-weight:600;font-size:29px;display:flex;align-items:center;gap:12px;opacity:.96}
.ftr .cta .chip{background:rgba(255,255,255,.18);border:1.5px solid rgba(255,255,255,.35);border-radius:999px;padding:6px 18px;font-size:26px}
/* body area */
.body{position:absolute;left:56px;right:56px;top:160px;bottom:140px}
.card{background:var(--surface);border:2px solid var(--line);border-radius:28px;box-shadow:0 2px 4px rgba(15,23,42,.04),0 24px 48px rgba(15,23,42,.08)}
.label{font-family:var(--en);font-weight:700;font-size:22px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.mark{background:linear-gradient(180deg, transparent 58%, var(--marker) 58%);padding:0 6px;border-radius:4px;color:var(--ink)}
.ruby{display:inline-block;position:relative;line-height:1;vertical-align:baseline}
.ruby .w{background:linear-gradient(180deg, transparent 60%, var(--marker) 60%);padding:0 4px;border-radius:4px;font-weight:600}
.ruby .g{display:block;text-align:center;font-family:var(--bn);font-size:.5em;color:var(--accent-deep);font-weight:600;line-height:1.1;margin-top:-.15em;white-space:nowrap}
.chip{display:inline-flex;align-items:center;gap:10px;height:46px;padding:0 18px;border-radius:999px;font-family:var(--en);font-weight:700;font-size:22px;letter-spacing:.02em}
.chip.pos{background:var(--tint);color:var(--accent-deep)}
.chip.beginner{background:var(--ok-tint);color:var(--ok)}
.chip.intermediate{background:var(--warn-tint);color:var(--warn)}
.chip.advanced{background:#fce7f3;color:#be185d}
.chip.cat{background:var(--surface);border:2px solid var(--line);color:var(--ink-2);font-family:var(--bn);font-size:24px;height:50px}
.muted{color:var(--muted)}
.en{font-family:var(--en)}
.serif{font-family:var(--en-display)}
.swipe{display:flex;align-items:center;gap:14px;font-family:var(--bn);font-weight:600;font-size:28px;color:var(--ink-2)}
.swipe .arrow{display:inline-flex;width:54px;height:54px;border-radius:50%;background:var(--ink);color:#fff;align-items:center;justify-content:center;font-family:var(--en);font-size:30px}
"""

FIT_JS = """
<script>
(function(){
  function limitOf(box){
    var cs = getComputedStyle(box);
    var h = (cs.maxHeight && cs.maxHeight !== 'none') ? parseFloat(cs.maxHeight) : box.clientHeight + 3;
    var w = (cs.maxWidth && cs.maxWidth !== 'none') ? parseFloat(cs.maxWidth) : box.clientWidth + 3;
    return {h: h, w: w};
  }
  function fit(el){
    var min = parseFloat(el.dataset.min||'18'), step = 1.5, guard = 90;
    var box = el.parentElement, lim = limitOf(box);
    var size = parseFloat(getComputedStyle(el).fontSize);
    while(guard-- > 0 && (el.scrollHeight > lim.h || el.scrollWidth > lim.w) && size > min){
      size -= step; el.style.fontSize = size + 'px';
    }
  }
  function run(){ document.querySelectorAll('.fit').forEach(fit); window.__fitDone = true; }
  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(run); } else { run(); }
})();
</script>
"""


def header_html(right: str = "") -> str:
    return (f'<div class="hdr"><div class="lockup"><img src="{logo_src()}" alt=""/>'
            f'<div class="wm">{esc(settings.WORDMARK[0])}<b>{esc(settings.WORDMARK[1] if len(settings.WORDMARK) > 1 else "")}</b></div></div><div>{right}</div></div>')


def footer_html(cta_bn: str | None = None, chip: str = "→") -> str:
    cta = cta_bn if cta_bn is not None else settings.STRINGS.get("footer_cta", "")
    return (f'<div class="ftr"><div class="url">{esc(settings.SITE_DISPLAY)}</div>'
            f'<div class="cta">{esc(cta)}<span class="chip">{esc(chip)}</span></div></div>')


def S(key: str, default: str = "", **fmt) -> str:
    """Project string (project.json → strings) with {placeholders}."""
    v = settings.STRINGS.get(key, default)
    try:
        return v.format(**fmt) if fmt else v
    except (KeyError, IndexError):
        return v


def _page(template: str, ctx: dict, height: int = settings.CANVAS[1]) -> str:
    html = (TPL / template).read_text(encoding="utf-8")
    c = settings.COLORS
    base = (BASE_CSS.replace("{{H}}", str(height)).replace("{{C_ACCENT}}", c["accent"]).replace("{{C_ACCENT_DEEP}}", c["accent_deep"])
            .replace("{{C_ACCENT_2}}", c["accent_2"]).replace("{{C_MARKER}}", c["marker"]).replace("{{C_PAPER}}", c["paper"])
            .replace("{{C_INK}}", c["ink"]))
    ctx = {"BASE_CSS": base, "FONT_CSS": font_css(), "FIT_JS": FIT_JS, **ctx}
    for k, v in ctx.items():
        html = html.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[A-Z_0-9]+\}\}", html)
    if left:
        raise ValueError(f"{template}: unreplaced tokens {sorted(set(left))}")
    return html


# ── markup helpers ─────────────────────────────────────────────────────────
def ruby(paragraph: str) -> str:
    """[[word|gloss]] → highlighted word with a small Bangla gloss above it."""
    def rep(m):
        w, g = m.group(1), (m.group(2) or "").strip()
        inner = f'<span class="w">{esc(w)}</span>'
        if g:
            inner = f'<span class="g">{esc(g)}</span>' + inner
        return f'<span class="ruby">{inner}</span>'
    out = esc(paragraph)
    out = re.sub(r"\[\[([^|\]]+)\|([^\]]*)\]\]", rep, out)
    out = re.sub(r"\[\[([^\]]+)\]\]", lambda m: f'<span class="mark">{m.group(1)}</span>', out)
    return out


def mark_hero(headline: str) -> str:
    out = esc(headline)
    return re.sub(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", r'<span class="mark">\1</span>', out)


def bold_html(text: str) -> str:
    return esc(text).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")


# ── Playwright ─────────────────────────────────────────────────────────────
def render_pages(pages: list[tuple[str, str, tuple[int, int]]], out_dir: Path) -> list[str]:
    """pages: [(filename, html, (w,h))] → PNG paths."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(device_scale_factor=settings.DEVICE_SCALE)
        for filename, html, (w, h) in pages:
            page = ctx.new_page()
            page.set_viewport_size({"width": w, "height": h})
            page.set_content(html, wait_until="load")
            try:
                page.wait_for_function("window.__fitDone === true", timeout=8000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(120)
            target = out_dir / filename
            page.screenshot(path=str(target), type="png", full_page=False)
            page.close()
            paths.append(str(target))
        ctx.close()
        browser.close()
    return paths


# ── pillar builders ────────────────────────────────────────────────────────
def _word_card_ctx(w: Word, i: int, n: int) -> dict:
    """Context for vocab.html; STORY_LINE is filled by the caller when a story exists."""
    sa = ""
    if w.synonym:
        sa += f'<div class="t"><span>সমার্থক</span>{esc(w.synonym)}</div>'
    if w.antonym:
        sa += f'<div class="t"><span>বিপরীত</span>{esc(w.antonym)}</div>'
    return {
        "SA_HTML": sa, "STORY_LINE": "", "INST_DISPLAY": "none",
        "WORD": esc(w.word), "PHONETIC": esc(w.phonetic), "POS": esc(w.pos or "word"),
        "DIFF": esc(w.difficulty), "DIFF_CLASS": w.difficulty.lower(),
        "GLOSS_BN": esc(w.gloss_bn), "MEANING_BN": esc(w.meaning_bn), "MEANING_EN": esc(w.meaning_en),
        "EXAMPLE_HTML": bold_html(w.example) if w.example else esc(w.meaning_en),
        "EXAMPLE_LABEL": "Example" if w.example else "Meaning", "IDX": str(i), "N": str(n),
    }


def _story_sentence(post: StoryPost, word: str) -> str:
    """The sentence from the story that contains `word` (markup stripped, word bolded)."""
    text = " ".join(s.paragraph for s in post.story_slides)
    plain = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", text)
    for sent in re.split(r"(?<=[.!?])\s+", plain):
        if re.search(rf"\b{re.escape(word)}", sent, re.I):
            return re.sub(rf"\b({re.escape(word)}\w*)", r"<b>\1</b>", esc(sent), count=1, flags=re.I)
    return ""


def render_story_post(post: StoryPost, out_dir: Path, date_str: str) -> list[str]:
    words = sorted(post.words, key=lambda w: 0 if w.word.lower() == post.hero_word.lower() else 1)
    n_story = len(post.story_slides)
    total = 1 + n_story + len(words) + 1
    pages = []
    cat_chip = (f'<span class="chip cat"><span class="emoji">{esc(post.category.icon)}</span>'
                f'{esc(post.category.bn)}</span>')
    hero = next((w for w in words if w.word.lower() == post.hero_word.lower()), words[0])
    pages.append(("slide_01_cover.png", _page("cover.html", {
        "HEADER": header_html(f'<span class="pill">1 / {total}</span>'),
        "FOOTER": footer_html(),
        "CAT_CHIP": cat_chip, "DATE": fmt_date(date_str),
        "KICKER": S("story_kicker", "Today") if post.pillar == "news_word" else S("story60_kicker", "৬০ সেকেন্ডের গল্প"),
        "HEADLINE_HTML": mark_hero(post.headline_en), "HEADLINE_BN": esc(post.headline_bn),
        "HERO_WORD": esc(hero.word), "HERO_GLOSS": esc(hero.gloss_bn), "HERO_POS": esc(hero.pos),
        "SWIPE_N": str(len(words)), "SWIPE_TEXT": S("swipe", "{n} words", n=len(words)),
    }), settings.CANVAS))
    for i, s in enumerate(post.story_slides, 1):
        pages.append((f"slide_{1+i:02d}_story.png", _page("story.html", {
            "HEADER": header_html(f'<span class="pill">{1+i} / {total}</span>'),
            "FOOTER": footer_html(S("story_footer", settings.STRINGS.get("footer_cta", ""))),
            "SECTION": esc(s.section_label.upper()), "PART": f"{i} / {n_story}" if n_story > 1 else "",
            "STORY_HTML": ruby(s.paragraph),
            "LEGEND": S("story_legend", ""),
        }), settings.CANVAS))
    base = 1 + n_story
    for i, w in enumerate(words, 1):
        ctx = _word_card_ctx(w, i, len(words))
        ctx.update({"HEADER": header_html(f'<span class="pill blue">Word {i} / {len(words)}</span>'),
                    "FOOTER": footer_html(S("word_footer", settings.STRINGS.get("footer_cta", ""))),
                    "STORY_LINE": _story_sentence(post, w.word)})
        ctx["INST_DISPLAY"] = "block" if ctx["STORY_LINE"] else "none"
        pages.append((f"slide_{base+i:02d}_word_{i}.png", _page("vocab.html", ctx), settings.CANVAS))
    rows = "".join(
        f'<div class="row"><div class="num">{i}</div><div class="w">{esc(w.word)}'
        f'<span class="pos">{esc(w.pos)}</span></div><div class="g">{esc(w.gloss_bn)}</div></div>'
        for i, w in enumerate(words, 1))
    pages.append((f"slide_{total:02d}_recap.png", _page("recap.html", {
        "HEADER": header_html(f'<span class="pill">{total} / {total}</span>'),
        "FOOTER": footer_html(),
        "N": str(len(words)), "ROWS": rows, "URL": esc(settings.SITE_DISPLAY),
        "RECAP_TITLE": S("recap_title", "Today's {n} words", n=len(words)), "RECAP_SUB": S("recap_sub", ""),
        "RECAP_CTA_HEAD": S("recap_cta_head", ""), "RECAP_CTA_SUB": S("recap_cta_sub", ""), "RECAP_CTA_BTN": S("recap_cta_button", "→"),
        "SOURCE": esc((post.source_title or post.topic)[:70]),
    }), settings.CANVAS))
    return render_pages(pages, out_dir)


def render_quiz(post: QuizPost, out_dir: Path) -> list[str]:
    letters = "ABCD"
    opts = "".join(f'<div class="opt"><span class="l">{letters[i]}</span><span>{esc(o)}</span></div>'
                   for i, o in enumerate(post.options))
    page = _page("quiz.html", {
        "HEADER": header_html('<span class="pill blue">Quiz</span>'),
        "FOOTER": footer_html("উত্তর কমেন্টে"),
        "WORD": esc(post.word.word), "PHONETIC": esc(post.word.phonetic), "POS": esc(post.word.pos),
        "QUESTION": esc(post.question_bn), "OPTIONS": opts, "EXAM": esc(post.exam_tag),
        "HINT": bold_html(post.word.example), "HINT_DISPLAY": "block" if post.word.example else "none",
        "QUIZ_KICKER": S("quiz_kicker_line", "Do you know this one?"), "QUIZ_NOTE": S("quiz_note", "Answer in the comments — the correct one is posted 6 hours later"),
    })
    return render_pages([("slide_01_quiz.png", page, settings.CANVAS)], out_dir)


def render_confusables(post: ConfusablesPost, out_dir: Path) -> list[str]:
    a, b = post.pair
    pages = [("slide_01_cover.png", _page("confusables_cover.html", {
        "HEADER": header_html('<span class="pill">1 / 3</span>'), "FOOTER": footer_html(),
        "TITLE_BN": esc(post.title_bn), "A": esc(a.word), "B": esc(b.word),
        "A_POS": esc(a.pos), "B_POS": esc(b.pos),
    }), settings.CANVAS)]
    cards = ""
    for w in (a, b):
        ex = f'<div class="ex en">{bold_html(w.example)}</div>' if w.example else f'<div class="ex en">{esc(w.meaning_en)}</div>'
        cards += (f'<div class="card wcard"><div class="w serif">{esc(w.word)}</div>'
                  f'<div class="ph en muted">{esc(w.phonetic)} · {esc(w.pos)}</div>'
                  f'<div class="gl">{esc(w.gloss_bn)}</div><div class="mb">{esc(w.meaning_bn)}</div>{ex}</div>')
    pages.append(("slide_02_pair.png", _page("confusables_pair.html", {
        "HEADER": header_html('<span class="pill">2 / 3</span>'), "FOOTER": footer_html("গুলিয়ে ফেলো না"),
        "CARDS": cards,
    }), settings.CANVAS))
    pages.append(("slide_03_rule.png", _page("confusables_rule.html", {
        "HEADER": header_html('<span class="pill">3 / 3</span>'), "FOOTER": footer_html("৩টি প্যাক ফ্রি"),
        "A": esc(a.word), "B": esc(b.word), "A_G": esc(a.gloss_bn), "B_G": esc(b.gloss_bn),
        "RULE": esc(post.difference_bn), "TIP": esc(post.memory_tip_bn),
        "TIP_BLOCK": "block" if post.memory_tip_bn else "none",
        "A_EX": bold_html(a.example) if a.example else esc(a.meaning_en),
        "B_EX": bold_html(b.example) if b.example else esc(b.meaning_en),
    }), settings.CANVAS))
    return render_pages(pages, out_dir)


def render_in_app(post: InAppPost, out_dir: Path) -> list[str]:
    shot = ASSETS / "screens" / post.screenshot
    src = _b64(shot, "image/png") if shot.exists() else ""
    page = _page("in_app.html", {
        "HEADER": header_html(f'<span class="pill blue">{S("in_app_kicker", "In the app")}</span>'),
        "FOOTER": footer_html("৩টি প্যাক ফ্রি"),
        "SHOT": src, "HEADLINE_BN": esc(post.headline_bn), "FACT": esc(post.fact_line),
        "NOTE": esc(post.feature_note_bn),
    })
    return render_pages([("slide_01_app.png", page, settings.CANVAS)], out_dir)


def render_offer(post: OfferPost, out_dir: Path) -> list[str]:
    page = _page("offer.html", {
        "HEADER": header_html(''), "FOOTER": footer_html("৩টি প্যাক ফ্রি"),
        "KIND": {"referral": "রেফারাল", "student": "স্টুডেন্ট অফার", "founder": "ফাউন্ডারের কথা",
                 "community": "কমিউনিটি", "free_path": "ফ্রি-তে শুরু"}.get(post.kind, ""),
        "HEADLINE_BN": esc(post.headline_bn), "BODY_BN": esc(post.body_bn), "DETAIL": esc(post.detail_line),
        "DETAIL_BLOCK": "flex" if post.detail_line else "none",
    })
    return render_pages([("slide_01_offer.png", page, settings.CANVAS)], out_dir)


def render_story_card(title_html: str, sub_bn: str, kicker: str, out_dir: Path, filename="story_1080x1920.png") -> str:
    page = _page("story_card.html", {
        "HEADER": header_html(""), "FOOTER": footer_html("৩টি প্যাক ফ্রি"),
        "KICKER": esc(kicker), "TITLE_HTML": title_html, "SUB_BN": esc(sub_bn), "PROFILE_UP": S("profile_up", "Full post on the profile ↑"),
    }, height=settings.STORY_CANVAS[1])
    return render_pages([(filename, page, settings.STORY_CANVAS)], out_dir)[0]
