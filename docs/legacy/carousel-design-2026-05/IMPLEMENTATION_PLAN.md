# StoryVocabs Carousel — Implementation Plan (for Claude Code / Haiku 4.5)

**Goal:** make `image_renderer.py` produce the four new 1080×1350 templates correctly from AI output, and make the AI emit a clean schema that drives them. Work the tasks **in order**; each has an acceptance test. Read `AUDIT.md` first — task IDs map to audit findings.

> **How to drive Haiku 4.5:** give it ONE task block at a time, paste the "Files," "Do," and "Acceptance" sections, and tell it to stop after the acceptance test passes. Do not let it refactor beyond the task. The templates in `templates/` are **final** — Haiku should treat their placeholder names as a fixed contract and never edit template HTML/CSS except where a task explicitly says so.

---

## 0. The single source of truth — JSON data contract

The AI writer (`story_writer.py`) must emit **exactly** this per post. Everything downstream maps from it. Lengths are **hard caps** — enforce in the prompt AND clamp in code.

```jsonc
{
  "post_label": "Post 2 — Deep Dive",
  "style": "long",                      // "short" | "long"
  "date": "2026-04-04",
  "category": { "en": "Sports", "bn": "খেলাধুলা", "icon": "🏏" },

  "headline_en": "Will [[punitive]] measures spoil Bangladesh–India cricket?",
  // hero word marked with [[ ]] in the headline; renderer wraps it in <span class="g">
  "hero_word": "punitive",
  "hero_gloss_bn": "শাস্তিমূলক · adjective",   // ≤ 4 words

  "story_slides": [                     // 1 for short, 1–2 for long. Pre-split by writer.
    {
      "section_label": "The Hook",      // ≤ 3 words, shown uppercased
      "paragraph": "As Bangladesh seeks closer ties, fans love more [[punitive|শাস্তিমূলক]] matches but [[bemoan|আক্ষেপ]] the gaps."
      // vocab words inline as [[english|short_bn_gloss]]; gloss ≤ 3 words
    }
  ],

  "words": [
    {
      "word": "Punitive",
      "pos": "adjective",                       // ≤ 12 chars
      "difficulty": "Intermediate",             // Beginner | Intermediate | Advanced
      "phonetic": "/ˈpjuːnɪtɪv/",               // optional, "" allowed
      "gloss_bn": "শাস্তিমূলক",                 // ≤ 3 words (for ruby + recap)
      "meaning_bn": "শাস্তি দেওয়ার উদ্দেশ্যে কৃত।",   // ≤ 14 words, 1–2 lines
      "meaning_en": "Intended as punishment.",        // ≤ 16 words, 1–2 lines
      "example": "The board faces <b>punitive</b> sanctions."  // 1 sentence, word in <b>; "" allowed
    }
  ],

  "word_count": 5,
  "quality_score": 8.0,
  "needs_review": false
}
```

**Deprecate/keep:** keep `full_story` only if other tooling needs it; the renderer no longer reads it. Drop the long `bangla`/`meaning` dictionary fields from the render path (keep in a `_debug` block if you want them for audits).

---

## TASK 1 — Fix renderer wiring (audit C1, C3, C5)
**Files:** `image_renderer.py`
**Do:**
1. Change template loads to the new names: `cover.html`, `story.html`, `vocab.html`, `closing.html`. Delete the three old `carousel_*.html` files.
2. Replace every `(1080, 1080)` and the `new_page(viewport=...)` with **`1080×1350`**. Keep `device_scale_factor=2`.
3. Fix the logo path: `Path(__file__).parent / "assets" / "logo-app-icon.png"` (no `static/`). Keep the base64 data-uri return.
**Acceptance:** `python -c "from image_renderer import get_logo_base64; print(get_logo_base64()[:30])"` prints a `data:image/png;base64,` prefix (non-empty). Grep confirms no `1080, 1080` and no `carousel_` remain.

## TASK 2 — Wait for self-fit before screenshot (audit M1, M2)
**Files:** `image_renderer.py`
**Do:** in the render loop, after `set_content(..., wait_until="networkidle")`, add
`page.wait_for_function("window.__fitDone === true", timeout=5000)` before `page.screenshot(...)`. Wrap in try/except that logs a warning but still screenshots (so a missing flag never hard-fails a batch).
**Acceptance:** render any post; logs show no timeout; no slide has clipped text at the bottom edge.

## TASK 3 — Rewrite the fill functions to the new contract (audit C2, C4, H4, H5)
**Files:** `image_renderer.py`
**Do:** delete `build_word_card`, `get_font_vars`, `FONT_TIERS`, `truncate_bangla`, `truncate_meaning`, and the old `render_bold`. Add small helpers:
- `wrap_hero(headline)` → replace `[[word]]` with `<span class="g">word</span>`.
- `ruby_markup(paragraph)` → replace `[[en|bn]]` with
  `<ruby class="vw"><span class="vw-en">en</span><rt><b>bn</b></rt></ruby>` (escape en/bn).
- `build_recap_rows(words)` → `<li><span class="n">i</span><span class="en">Word</span><span class="bn">gloss_bn</span></li>`.

Then fill per slide using the contract tokens. Slide order & filenames:
```
slide_1_cover.png
slide_2_story.png   (… slide_3_story.png if 2 story slides)
slide_N_vocab_1.png … slide_N_vocab_K.png   (one per word)
slide_last_closing.png
```
- **Cover:** LOGO_SRC, SLIDE_NUMBER=1, TOTAL_SLIDES, CATEGORY_ICON, CATEGORY(.en), DATE(formatted), HEADLINE_HTML=`wrap_hero(headline_en)`, HERO_WORD, HERO_BN=hero_gloss_bn, SWIPE_COUNT=word_count.
- **Story (loop story_slides):** SECTION_LABEL, SLIDE_NUMBER, TOTAL_SLIDES, STORY_PARAGRAPH=`ruby_markup(paragraph)`, CTA_LABEL (Bangla, fixed string), APP_URL=`storyvocabs.vercel.app`.
- **Vocab (loop words):** WORD_INDEX, WORD_TOTAL=word_count, POS, DIFFICULTY, DIFF_CLASS=`difficulty.lower()`, WORD, PHONETIC (may be ""), MEANING_BN=meaning_bn, MEANING_EN=meaning_en, EXAMPLE_HTML=example **or "" if blank** (the template hides empty), CTA_LABEL, APP_URL.
- **Closing:** SLIDE_NUMBER=TOTAL, TOTAL_SLIDES, WORD_TOTAL, RECAP_ROWS_HTML=`build_recap_rows(words)`, CTA_LABEL, APP_URL.

`TOTAL_SLIDES = 1 + len(story_slides) + len(words) + 1`. Cap at 20; if exceeded, drop the closing slide first, then merge story slides.
**Acceptance:** rendered slides contain **no literal `{{…}}`** text (grep the page content via Playwright, or eyeball). Counter reads correctly on every slide.

## TASK 4 — Add the missing AI fields (audit H1, H2, H3, H6, L4)
**Files:** `story_writer.py` (prompt + JSON parsing/validation)
**Do:** update the system/user prompt to emit the **TASK 0 contract**. Add explicit instructions + caps:
- `gloss_bn` ≤ 3 words; `meaning_bn` ≤ 14 words; `meaning_en` ≤ 16 words; `pos` lowercase; `difficulty` one of the three; `phonetic` IPA or "".
- headline must contain exactly one `[[word]]`; each `paragraph` must contain ≥1 `[[en|bn]]`.
- `example` must be a real sentence containing the word in `<b>…</b>`.
- writer picks `category` from the **story content**, not the news genre slot.
Add a validator that clamps over-length fields (truncate at word boundary + "…") and fills safe defaults (`phonetic=""`, `example=""`) so a sloppy model never breaks rendering.
**Acceptance:** generate one post; assert every word has all 7 keys, all within caps; headline has one `[[ ]]`; each paragraph has a `[[|]]`.

## TASK 5 — Re-tune story splitting for 1080×1350 (audit M1, M5)
**Files:** `story_writer.py` (preferred — writer pre-splits) or `image_renderer.py`
**Do:** target **≤ ~55 words per story slide** for "long" posts (the embedded auto-fit handles the rest). Short = 1 slide; long = 1–2. Remove the old char-count tier logic. If the writer pre-splits into `story_slides`, the renderer just loops — no splitting code needed (delete `split_content_smart`).
**Acceptance:** a 150-word long post yields 2 story slides, neither clipped (auto-fit `--k`/font never hits its floor visibly).

## TASK 6 — Embed fonts for deterministic rendering (audit M3, M4)
**Files:** `image_renderer.py`, render environment
**Do:** download Inter + Noto Sans Bengali `woff2`, base64-embed them via an injected `@font-face` `<style>` (replace the Google `<link>` at render time, or inline in templates). Install `fonts-noto-color-emoji` in the render container so category/CTA emoji render in color. Verify Bangla glyphs render with no network.
**Acceptance:** disconnect network (or block fonts.googleapis.com) and render — Bangla still renders correctly; emoji are color, not boxes.

## TASK 7 — Config hygiene (audit L1, L2)
**Files:** `config.py`
**Do:** replace `INSTAGRAM_SIZE`/`FACEBOOK_SIZE` with a single `CANVAS = (1080, 1350)` and import it in the renderer. Confirm all CTA/caption URLs are `storyvocabs.vercel.app` (already correct in config; templates fixed). 
**Acceptance:** grep shows no `netlify`, no `1080, 1080`; one `CANVAS` constant used by the renderer.

## TASK 8 — Tighten quality scoring (audit L3)
**Files:** `story_writer.py` (scorer prompt)
**Do:** add a "natural-fit" sub-score: penalize words shoehorned into unrelated context (e.g. a tax term in a misinformation story). Reject (`needs_review=true`) if any word's usage is semantically forced, even if the overall score ≥ 7.
**Acceptance:** feed the known-bad April-13 post 4 (Excise in a misinformation story) — it flags `needs_review=true`.

---

## Verification harness
`index.html` in this project is the **reference renderer**: it implements TASK 0 + TASK 3 in JavaScript and renders a real post to all slides in the browser. Use it to (a) eyeball the target output and (b) copy the exact token-mapping logic into Python. If Python output and `index.html` output diverge for the same JSON, Python is wrong.

## Done = all green
1–8 complete, `index.html` and Python render the same sample identically, no clipping, no `{{ }}`, logo + Bangla + emoji all present, ≤20 slides.
