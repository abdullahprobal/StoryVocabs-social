# StoryVocabs Social Media Automation

Automatically generates daily vocabulary content for StoryVocabs Facebook & Instagram.

## Quick Start

```bash
# 1. Install dependencies (one-time)
pip install -r requirements.txt
playwright install chromium

# 2. Add your Groq API key
#    Copy from main app's .env → paste into .env here

# 3. Generate today's content
python generate.py
```

## Commands

| Command | What it does |
|---------|-------------|
| `python generate.py` | Full pipeline: news → AI story → images → caption |
| `python generate.py --story-only` | Generate story text only (no images) |
| `python generate.py --manual "Your headline"` | Use your own headline instead of news |

## Output

All files land in `output/YYYY-MM-DD/`:
- `slide_1_cover.png` — Carousel cover (1080×1080)
- `slide_2_story.png` — Story page 1
- `slide_3_story.png` — Story page 2
- `slide_4_story.png` — Story page 3
- `slide_5_vocab.png` — Vocabulary summary
- `reel_overlay.png` — Reel text card (1080×1920)
- `whatsapp.png` — WhatsApp forwardable (800×800)
- `caption.txt` — Ready-to-paste caption with hashtags
- `content.json` — Raw AI output

## Posting Flow (30 seconds)

1. Script auto-opens Meta Business Suite
2. Caption auto-copied to clipboard
3. Click "Create Post" → Paste caption
4. Upload the 5 carousel slides
5. Schedule or publish

## Design Language

Uses StoryVocabs brand system:
- **Colors:** Blue `#3b82f6` → Purple `#8b5cf6` gradient
- **Font:** Inter + Noto Sans Bengali
- **Style:** Glass morphism, clean, premium

## This project is independent

This folder has its own `.git/` — it never touches the main Story-Vocabulary app repo.
