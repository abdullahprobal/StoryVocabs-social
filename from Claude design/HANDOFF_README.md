# Handoff: StoryVocabs Carousel System

## Overview

A production-ready carousel template system for Instagram/Facebook social media posts. This system renders 4:5 portrait slides (1080×1350px) with dark premium ed-tech styling, combining a cover headline, story narrative with inline vocabulary glosses, individual word hero cards, and a recap closing slide.

The carousel automatically generates from a single JSON data contract, self-fits text to prevent overflow, and is built to be driven by an AI content pipeline (generates daily posts with news-sourced vocabulary).

## Fidelity

**High-fidelity (hifi)**: Pixel-perfect dark-mode responsive templates with final colors, typography, spacing, and interactions. The developer should port these templates into the Python image renderer (`image_renderer.py`) to generate PNG carousels for posting to social media.

## Files in This Handoff

- **`IMPLEMENTATION_PLAN.md`** — The data contract + 8 ordered, testable tasks
- **`AUDIT.md`** — Complete bug audit (what's broken, why, where to fix)
- **`templates/cover.html`** — Slide 1: hero headline + hook word
- **`templates/story.html`** — Slide 2+: narrative with inline vocabulary (ruby gloss)
- **`templates/vocab.html`** — Slide 3–N: single-word hero cards
- **`templates/closing.html`** — Final slide: recap list + download CTA
- **`index.html`** — Live reference renderer (QA harness; edit JSON → see all slides)

## The Single Source of Truth: JSON Data Contract

Every post is one JSON blob (see IMPLEMENTATION_PLAN.md § 0 for full schema):

```json
{
  "post_label": "Post 4 — Deep Dive",
  "style": "long",
  "date": "2026-04-04",
  "category": { "en": "Sports", "bn": "খেলাধুলা", "icon": "🏏" },
  "headline_en": "Will [[punitive]] measures spoil Bangladesh–India cricket?",
  "hero_word": "Punitive",
  "hero_gloss_bn": "শাস্তিমূলক · adjective",
  "story_slides": [
    {
      "section_label": "The Hook",
      "paragraph": "As Bangladesh seeks closer ties, fans love more [[punitive|শাস্তিমূলক]] matches…"
    }
  ],
  "words": [
    {
      "word": "Punitive",
      "pos": "adjective",
      "difficulty": "Intermediate",
      "phonetic": "/ˈpjuːnɪtɪv/",
      "gloss_bn": "শাস্তিমূলক",
      "meaning_bn": "শাস্তি দেওয়ার উদ্দেশ্যে কৃত।",
      "meaning_en": "Intended as punishment.",
      "example": "The board faces <b>punitive</b> sanctions."
    }
  ],
  "word_count": 5,
  "quality_score": 8.0,
  "needs_review": false
}
```

**Key markup tokens:**
- `[[word]]` in headline → wraps word in `<span class="g">` (gradient text)
- `[[en|bn]]` in paragraphs → renders as `<ruby>` with Bangla gloss pill under English word
- All text fields auto-cap at defined lengths (see IMPLEMENTATION_PLAN.md)

## Slides Overview

| Slide | Purpose | Key Elements |
|-------|---------|--------------|
| **Cover (1)** | Scroll-stopper | Category pill, date, headline with hero word highlighted, "swipe to learn N words" CTA |
| **Story (1–2)** | Narrative context | Section label, paragraph with ruby-glossed vocab, download CTA |
| **Vocab (1 per word)** | Hero word card | Giant gradient word, phonetic IPA, short Bangla meaning + English definition, example sentence |
| **Closing (1)** | Recap + exit CTA | List of all words (number, English, short Bangla gloss), "save this post" button, app URL |

## Design System

### Colors (CSS variables in templates)
- `--ink: #0f172a` (near-black background)
- `--blue: #3b82f6`, `--blue-bright: #60a5fa`
- `--purple: #8b5cf6`, `--purple-bright: #a78bfa`
- `--grad: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)` (primary gradient)
- `--white: #f8fafc`, `--slate-*` (text neutrals)
- `--surface: rgba(255,255,255,0.05)` (cards, hover)

### Typography
- **Font families:** `Inter` (English), `Noto Sans Bengali` (Bangla)
- **Headlines:** 74px, 800wt, -0.035em letter-spacing
- **Body:** 47px (story), 30–42px (vocab), line-height 1.5–2.35
- **Labels:** 22–26px, 800wt, 0.16em letter-spacing

### Spacing & Layout
- Canvas: **1080×1350px** (4:5 portrait, IG/FB feed-optimal)
- Padding: 60–72px horizontal, 150–200px top/bottom
- Gap: 18–48px between elements
- Border radius: 12–24px on cards/sections

### Self-Fitting (embedded in each template)
Each slide has a `<script>` that auto-shrinks text if content overflows:
- **Cover:** headline shrinks from 74px → 40px min
- **Story:** paragraph shrinks from 47px → 26px min, line-height tightens
- **Vocab/Closing:** scale all content via `--k` multiplier (1.0 → 0.55)
Sets `window.__fitDone = true` when done (renderer waits on this).

## Interactions & Behavior

### Carousel Navigation
- User swipes left (mobile) or clicks next (web) to move through slides
- Slide counter shows "N / TOTAL" on every slide
- No animations needed for static PNG carousel

### CTA Buttons
- Every slide has a gradient-background footer with Bangla label + app URL
- Story slides: "📖 গল্পে শব্দ শিখতে ডাউনলোড করো" + `storyvocabs.vercel.app`
- Vocab slides: "📲 আরও শব্দ শিখতে ডাউনলোড করো" + `storyvocabs.vercel.app`
- Closing: "📲 প্রতিদিন এভাবে শিখতে অ্যাপটি ডাউনলোড করো" + save button

### Responsive Behavior
Templates are fixed-size for social media (1080×1350 is non-negotiable). On the renderer side, Playwright renders at 2× device scale (2160×2700) and exports PNG at standard (1080×1350).

## State & Data Flow

1. **AI writer** (`story_writer.py`) emits the JSON contract above.
2. **Image renderer** (`image_renderer.py`) reads the JSON and fills template placeholders.
3. **Playwright** renders HTML → PNG at 1080×1350 (device_scale_factor=2).
4. Renderer waits for `window.__fitDone = true` before screenshotting (self-fit safety).
5. PNGs are saved, captions built, carousel posted to Meta Business Suite.

## Migration Path (for Claude Code)

See `IMPLEMENTATION_PLAN.md` for the 8 ordered tasks:

1. **Task 1**: Fix renderer wiring (filenames, canvas size, logo path)
2. **Task 2**: Wait for `window.__fitDone` before screenshot
3. **Task 3**: Rewrite fill functions to new token contract ← *the critical rewrite*
4. **Task 4**: Add missing AI fields to the prompt (`gloss_bn`, `phonetic`, short meanings, `[[ ]]` markup)
5. **Task 5**: Re-tune story splitting for 1080×1350
6. **Task 6**: Embed fonts for offline-safe Bangla rendering
7. **Task 7**: Config hygiene (single `CANVAS` constant)
8. **Task 8**: Tighten quality scoring

Do **one task at a time**. Each has an acceptance test; stop after it passes and wait for feedback before proceeding.

## QA Harness

**`index.html`** is a live reference renderer:
- Left panel: JSON editor + "Quick Bite" / "Deep Dive" sample toggle
- Right: gallery of all carousel slides (the preview)
- Edit the JSON, click "Render carousel →", and see all slides update instantly

Use this to:
1. Verify the data contract works end-to-end
2. Compare Python output vs. JS output (they should be identical)
3. Test edge cases (long text, many words, empty fields)

## Assets

- **Logo**: `assets/logo-app-icon.png` (168×195, PNG, rounded corners)
- **Fonts**: Inter + Noto Sans Bengali (loaded from Google Fonts CDN; Task 6 embeds them)
- **Emoji**: Category icons (🏏 🏛️ 💰 🌿 etc.) — require `fonts-noto-color-emoji` in render environment

## Known Constraints

- Max 20 slides per carousel (Instagram limit)
- All text is capped at word boundaries (see contract for caps)
- Bangla text MUST have `Noto Sans Bengali` or glyphs will fail
- HTML templates are read-only for the renderer — treat `{{ }}` placeholders as a fixed interface
- No responsive media queries — 1080×1350 is the only canvas size

## Next Steps

1. **Download** this handoff folder + `index.html` from the original project
2. **Test** the live renderer: open `index.html`, toggle samples, edit JSON, verify all slides render
3. **Hand to Claude Code**: feed it `IMPLEMENTATION_PLAN.md` + `AUDIT.md` + this README + Tasks 1–8
4. **Iterate task-by-task**: stop after each acceptance test, review output, proceed to next

---

**Questions?** Refer to `AUDIT.md` for the "why" behind each task, and `IMPLEMENTATION_PLAN.md` § 0 for the full data contract.
