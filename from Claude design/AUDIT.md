# StoryVocabs Carousel — System Audit

**Date:** May 29, 2026
**Scope:** `templates/*.html` (new 4:5 design) ↔ `image_renderer.py`, `generate.py`, `config.py`, real `output/**/content.json`
**Verdict:** The new templates are well-designed, but **the pipeline cannot render them as-is.** A `generate.py` run today would produce broken or empty slides. Issues below are grouped by severity with the exact fix location. The companion `IMPLEMENTATION_PLAN.md` turns every CRITICAL/HIGH item into an ordered task list.

---

## 🔴 CRITICAL — system is broken end-to-end

### C1. Template filenames don't match what the renderer loads
`image_renderer.py` calls `load("carousel_cover.html")`, `load("carousel_story.html")`, `load("carousel_vocab.html")`.
The new templates are named **`cover.html`, `story.html`, `vocab.html`**.
→ Either `FileNotFoundError`, or it silently renders the **old** square templates if they still exist. **Fix:** rename loads (and delete the old `carousel_*` files).

### C2. Placeholder contracts are almost entirely disjoint
The renderer fills the **old** tokens; the new templates expect **different** tokens. Almost nothing overlaps, so most `{{...}}` would render **literally as text** on the image.

| Slide | Renderer emits (old) | New template expects |
|---|---|---|
| Cover | `{{TITLE}} {{CATEGORY}} {{DATE}} {{WORD_COUNT}} {{POST_LABEL}} {{CATEGORY_ICON}}` | `{{HEADLINE_HTML}} {{HERO_WORD}} {{HERO_BN}} {{SWIPE_COUNT}} {{SLIDE_NUMBER}} {{TOTAL_SLIDES}} {{CATEGORY}} {{CATEGORY_ICON}} {{DATE}}` |
| Story | `{{FONT_VARS}} {{SECTION_LABEL}} {{SLIDE_NUM}} {{HOOK_HTML}} {{STORY_HTML}} {{EXTRA_HTML}}` | `{{SECTION_LABEL}} {{SLIDE_NUMBER}} {{TOTAL_SLIDES}} {{STORY_PARAGRAPH}} {{CTA_LABEL}} {{APP_URL}}` |
| Vocab | `{{WORDS_HTML}} {{WORD_COUNT}} {{EXAM_NOTE}} {{PAGE_DOTS}}` | `{{WORD_INDEX}} {{WORD_TOTAL}} {{POS}} {{DIFFICULTY}} {{DIFF_CLASS}} {{WORD}} {{PHONETIC}} {{MEANING_BN}} {{MEANING_EN}} {{EXAMPLE_HTML}} {{CTA_LABEL}} {{APP_URL}}` |

**Fix:** rewrite the renderer's fill logic to the new contract (canonical contract is defined in the plan).

### C3. Canvas size is hardcoded to the old square ratio
Renderer pushes `(1080, 1080)` for every slide and `new_page(viewport={"width":1080,"height":1080})`. New templates are **1080×1350**. → bottom **270px** (incl. the entire CTA/swipe bar) is cropped, and the 4:5 layout renders into a 1:1 box. **Fix:** all sizes → `1080×1350`.

### C4. One-word-per-slide vs. three-words-per-slide
The new `vocab.html` is a **single-word hero card**. The renderer batches **3 words** into `{{WORDS_HTML}}` via `build_word_card()` (a multi-card list that no longer exists in the template). → guaranteed mismatch. **Fix:** loop one vocab slide per word.

### C5. Logo path is wrong → logo missing on every slide
`get_logo_base64()` reads `Path(__file__).parent / "static" / "logo-app-icon.png"`. The asset actually lives at **`assets/logo-app-icon.png`** (no `static/` dir). The function returns `""` → `<img src="">`, a broken logo on all slides. **Fix:** point to `assets/`.

---

## 🟠 HIGH — data the templates need does not exist in the AI output

Real sample (`output/2026-04-13/post_4_content.json`) `words[]` items contain: `word, bangla, meaning, pos, sentence, _pack_id, _difficulty`. The new templates need fields that are **absent or wrong-shaped**:

### H1. No short Bangla gloss (`gloss_bn`)
Both the cover hero chip and the story `<ruby>` need a **1–3 word** Bangla gloss. The only Bangla present is `bangla` — an **encyclopedic run-on** (e.g. *Aftermath* = a 30+ word sentence). Dropping that into the ruby pill or hero chip overflows catastrophically. **Fix:** add `gloss_bn` to the AI schema (hard cap ~3 words).

### H2. No phonetic / IPA
`vocab.html` has a `{{PHONETIC}}` slot; the data has no IPA anywhere. **Fix:** add optional `phonetic`; template already tolerates blank.

### H3. `bangla` and `meaning` are far too long for the card slots
`{{MEANING_BN}}` and `{{MEANING_EN}}` are designed for ~1–2 lines. Real values are multi-clause dictionary prose. → vertical overflow / clipping on the vocab card. **Fix:** add concise `meaning_bn` / `meaning_en` (capped) **and** keep the auto-fit safety net (below).

### H4. `sentence` is usually empty
All 5 words in the sample have `"sentence": ""`. The example block would render an empty `" "`. **Fix:** template hides the example when blank (done in the finalized template) — and the prompt should require a sentence.

### H5. Story word-markup format mismatch
`full_story` uses `**Word** (বাংলা)` inline. The new story template wants `<ruby>` markup with a **short** gloss. The old `render_bold()` produces `<span class="vw">`/`<span class="bn">` which the new template doesn't style. **Fix:** emit a clean inline token (`[[word|gloss_bn]]`) and convert to `<ruby>` in the renderer.

### H6. `_difficulty` is internal & monotonous
Field is prefixed `_` (treated as internal/debug) and **every** sampled word is `"Beginner"`. The template's `{{DIFF_CLASS}}` needs lowercase `beginner|intermediate|advanced`. **Fix:** promote to a real `difficulty` field; make the word-pack data carry genuine levels.

---

## 🟡 MEDIUM — overflow, robustness, dead code

### M1. Story type is enormous → real stories will clip
`story.html` `.para` is `47px / line-height 2.35` inside a fixed ~990px-tall box. That fits only ~7–8 lines. A 150-word "Deep Dive" story is far longer → it overflows a `overflow:hidden` body and gets **cut off** with no warning. **Fix:** embed an **auto-fit** script in the template (shrinks font to fit) **and** keep paragraph-splitting across story slides. (Auto-fit is baked into the finalized `story.html`.)

### M2. No render-time overflow guard anywhere
Same risk on the vocab card with long meanings. **Fix:** auto-fit safety net baked into `vocab.html`.

### M3. Fonts loaded from CDN at render time
Templates pull Inter + Noto Sans Bengali via `<link>` and the renderer waits on `networkidle`. If the CDN is slow/unavailable in the render environment, Bangla falls back to a system font (or tofu). **Fix:** self-host / base64-embed both fonts for deterministic, offline-safe rendering. **Critical for Bangla.**

### M4. Emoji in headless Chromium
Category icons + CTA emoji (🏏 💡 📲 🇧🇩) need a color-emoji font installed in the render container, or they render as boxes. **Fix:** install `fonts-noto-color-emoji` in the render environment (or replace category icons with SVG/inline glyphs).

### M5. Dead / orphaned renderer code
`FONT_TIERS`, `get_font_vars()`, `build_word_card()`, `truncate_bangla()`, `truncate_meaning()`, `render_bold()`, `split_content_smart()`'s 3-word logic — all assume the old design. Once the new contract lands, most of this is dead or needs rewriting. **Fix:** remove/replace; keep only sentence-aware splitting (retargeted to 1080×1350).

---

## 🔵 LOW — consistency & config hygiene

### L1. App URL is inconsistent (confirmed: `storyvocabs.vercel.app` is correct)
`config.py` captions say `storyvocabs.vercel.app`; the new templates say `storyvocabs.netlify.app`. **Fix:** templates → `vercel.app` everywhere. (Done in finalized templates.)

### L2. `config.py` size constants contradict the design
`INSTAGRAM_SIZE=(1080,1080)`, `FACEBOOK_SIZE=(1200,1080)` — neither is the 1080×1350 the design uses (and the renderer ignores them anyway). **Fix:** set a single `CANVAS=(1080,1350)` and use it.

### L3. Quality scoring is lenient
Post 4 shoehorns *Excise* (a tax term) into a misinformation story yet scored **8.0/10** against a 7.0 threshold. Word-topic alignment can produce forced fits the scorer waves through. **Fix:** tighten the rubric to penalize semantically forced word usage; raise threshold or add a "natural-fit" sub-score.

### L4. Category label looseness
`category.en = "Politics & Governance"` on a story that's really about a misinformation video. Minor, but affects the icon + caption. **Fix:** allow the writer to pick the category from the story, not the news genre slot.

---

## What "good" looks like (target state)

1. One JSON schema (defined in the plan) is the single source of truth.
2. The AI emits short, capped fields (`gloss_bn`, `meaning_bn`, `meaning_en`, `phonetic`, `difficulty`, sentence required) **plus** story text with `[[word|gloss_bn]]` tokens.
3. The renderer maps that schema 1:1 onto the new placeholder contract, at 1080×1350, with fonts embedded.
4. Templates self-defend against length via embedded auto-fit, so no slide ever clips.
5. Carousel = **Cover → Story×(1–2) → Vocab×N → Closing**, ≤ 20 slides.
