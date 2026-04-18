# StoryVocabs Social Media Automation — System Handover Document

**Date:** April 4, 2026  
**Version:** 2.0  
**Prepared by:** AI Engineer  
**Handover to:** StoryVocabs Team / Successor Engineer  

---

## 1. System Overview

### 1.1 Purpose

StoryVocabs Social Media Automation is a Python-based pipeline that automatically generates daily vocabulary content for Facebook and Instagram. Each day it:

1. Fetches trending Bangladesh news filtered by a weekly genre schedule
2. Selects 5 vocabulary words from the app's word packs (never reusing a word >3 times/year)
3. Writes a bilingual (Bangla+English) news story using Groq AI (Llama 3.3 70B)
4. Runs a quality check (must score ≥6.0/10)
5. Renders HD 1080×1080 PNG slides with the StoryVocabs app logo and CTA bar
6. Copies the caption to clipboard and opens Meta Business Suite for posting

### 1.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate project from main app | Prevents git conflicts, keeps app repo clean |
| Word packs drive content (not AI-generated words) | Ensures alignment with app curriculum |
| Groq API (free tier) | 100K tokens/day free, Llama 3.3 70B model |
| Playwright for image rendering | HTML/CSS templates → pixel-perfect PNGs |
| Daily genre schedule | Ensures content variety across the week |
| Story tracking (6-month gap) | Prevents repeating the same news story |

---

## 2. System Architecture

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    STORYVOCABS-SOCIAL                         │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   Word Pack  │    │   News       │    │   Story      │    │
│  │   Manager    │    │   Scraper    │    │   Writer     │    │
│  │              │    │              │    │              │    │
│  │ Loads words  │───→│ Fetches BD   │───→│ Groq AI      │    │
│  │ from app's   │    │ news by      │    │ generates    │    │
│  │ JS files     │    │ genre        │    │ bilingual    │    │
│  └──────────────┘    └──────────────┘    │ story        │    │
│                                           └──────┬───────┘    │
│                                                  │            │
│                                                  ▼            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │   Caption    │    │   Image      │    │   Quality    │    │
│  │   Builder    │←───│   Renderer   │←───│   Checker    │    │
│  │              │    │              │    │              │    │
│  │ Builds FB/IG │    │ Playwright   │    │ Scores story │    │
│  │ caption with │←───│ renders HTML │    │ ≥6.0/10 to   │    │
│  │ hashtags     │    │ → PNG slides │    │ pass         │    │
│  └──────┬───────┘    └──────────────┘    └──────────────┘    │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────────┐                                     │
│  │   Clipboard + MBS    │                                     │
│  │   (PowerShell)       │                                     │
│  │                      │                                     │
│  │ Auto-copies caption  │                                     │
│  │ Opens Meta Business  │                                     │
│  │ Suite in browser     │                                     │
│  └──────────────────────┘                                     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Word Packs (JS) → candidates (10 words)
News RSS + Google News → filtered articles (by genre)
AI Prompt (news + words) → Groq API → JSON story
Quality Check → Pass/Fail → Revise if needed
HTML Templates + Data → Playwright → PNG slides
Caption Template + Data → UTF-8 text → Clipboard
```

---

## 3. Deployment Environment

### 3.1 Local Machine (Current)

| Property | Value |
|----------|-------|
| **OS** | Windows 11 |
| **Python** | 3.14 (C:\Python314) |
| **Location** | `C:\Users\DELL\.antigravity\StoryVocabs-social\` |
| **Git** | Independent repo (separate from main app) |
| **Shell** | PowerShell |

### 3.2 Prerequisites

```
Python 3.10+ (tested on 3.14)
pip (Python package manager)
Playwright Chromium browser
Groq API account (free tier: 100K tokens/day)
Meta Business Suite account (for posting)
```

### 3.3 External Services

| Service | Purpose | Cost | Limit |
|---------|---------|------|-------|
| **Groq API** | AI story generation | Free | 100K tokens/day |
| **Google News RSS** | News fetching | Free | None |
| **News RSS Feeds** | BD news sources | Free | None |
| **Meta Business Suite** | Scheduling posts | Free | None |
| **Google Fonts CDN** | Inter + Noto Sans Bengali | Free | None |

---

## 4. Configuration Files

### 4.1 `.env`

```
GROQ_API_KEY=gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

- **Required:** Yes
- **Source:** https://console.groq.com/keys
- **Note:** Same key as main app's `frontend/.env`
- **Security:** Listed in `.gitignore`, never committed

### 4.2 `config.py`

| Setting | Description |
|---------|-------------|
| `GROQ_MODEL` | AI model: `llama-3.3-70b-versatile` |
| `GENRE_SCHEDULE` | 7-day genre mapping (Mon-Sun) |
| `NEWS_SOURCES` | 6 RSS feed URLs |
| `CAPTION_TEMPLATE` | Post caption format |
| `HASHTAG_POOL` | 21 hashtags for rotation |
| `INSTAGRAM_SIZE` | (1080, 1080) |

### 4.3 `story_usage_tracker.json`

Auto-generated. Tracks which news stories have been used:
```json
{
  "hollowingouttheeconomybyillicitfundoutflow": [
    {"date": "2026-03-31", "title": "Hollowing out the economy..."}
  ]
}
```

### 4.4 `word_usage_tracker.json`

Auto-generated. Tracks word usage per year:
```json
{
  "infrastructure": {
    "2026": 1,
    "dates": ["2026-03-30"]
  }
}
```

---

## 5. Dependency List

### 5.1 Python Packages (`requirements.txt`)

```
groq>=0.4.0          # Groq API client
feedparser>=6.0       # RSS feed parsing
requests>=2.31        # HTTP requests
playwright>=1.40      # Browser automation (HTML → PNG)
python-dotenv>=1.0    # .env file loading
Pillow>=10.0          # Image processing
moviepy>=1.0          # Video creation (future use)
```

### 5.2 System Dependencies

```
Chromium browser (installed via: python -m playwright install chromium)
```

### 5.3 Install Commands

```powershell
cd C:\Users\DELL\.antigravity\StoryVocabs-social
pip install -r requirements.txt
python -m playwright install chromium
```

---

## 6. File Structure

```
StoryVocabs-social/
│
├── .env                          # Groq API key (DO NOT COMMIT)
├── .gitignore                    # Ignores output/, .env, __pycache__/
├── config.py                     # All settings, genre schedule, hashtags
├── generate.py                   # Master script — runs entire pipeline
├── generate.ps1                  # PowerShell launcher
├── RUN.bat                       # Double-click launcher
├── requirements.txt              # Python dependencies
├── README.md                     # Project docs
│
├── word_pack_manager.py          # Loads word packs from app JS files
├── news_scraper.py               # Fetches + filters news by genre
├── story_writer.py               # Groq AI story generation + quality check
├── image_renderer.py             # Playwright HTML → PNG rendering
│
├── templates/
│   ├── carousel_cover.html       # Slide 1: Cover card
│   ├── carousel_story.html       # Slides 2-N: Story paragraphs
│   └── carousel_vocab.html       # Last slide: Vocabulary cards
│
├── static/
│   └── logo-app-icon.png         # StoryVocabs app logo (copied from app)
│
├── output/                       # Generated content (date folders)
│   ├── 2026-03-31/
│   │   ├── slide_1_cover.png
│   │   ├── slide_2_story.png
│   │   ├── slide_3_story.png
│   │   ├── slide_4_vocab.png
│   │   ├── caption.txt
│   │   └── content.json
│   └── ...
│
├── story_usage_tracker.json      # News story dedup tracking
└── word_usage_tracker.json       # Word frequency tracking
```

---

## 7. Weekly Genre Schedule

| Day | Genre (Bangla) | Genres (English) |
|-----|---------------|------------------|
| Monday | প্রযুক্তি ও ব্যবসা | Technology, Business |
| Tuesday | প্রযুক্তি ও ব্যবসা | Technology, Business |
| Wednesday | ব্যবসা ও প্রযুক্তি (সম্পাদকীয়) | Business, Technology (editorial) |
| Thursday | রাজনীতি ও ক্রিকেট | Politics, Cricket, History |
| Friday | রাজনীতি ও ক্রিকেট | Politics, Cricket, Geopolitics |
| Saturday | রাজনীতি, ক্রিকেট ও ইতিহাস | Politics, Cricket, History |
| Sunday | রাজনীতি ও ভূ-রাজনীতি (সম্পাদকীয়) | Politics, Geopolitics (editorial) |

---

## 8. API Documentation

### 8.1 Groq API

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.groq.com/openai/v1/chat/completions` |
| **Model** | `llama-3.3-70b-versatile` |
| **Auth** | Bearer token via `GROQ_API_KEY` env var |
| **Rate Limit** | 100K tokens/day (free tier) |
| **Reset** | Midnight UTC (6:00 AM Bangladesh time) |

### 8.2 RSS Feeds

| Source | URL |
|--------|-----|
| The Daily Star | `https://www.thedailystar.net/rss.xml` |
| Dhaka Tribune | `https://www.dhakatribune.com/rss` |
| BD News 24 | `https://bdnews24.com/rss` |
| Prothom Alo (EN) | `https://en.prothomalo.com/rss` |
| TBS News | `https://www.tbsnews.net/rss` |
| Financial Express | `https://www.thefinancialexpress-bd.com/rss` |

---

## 9. Security Controls

| Control | Status |
|---------|--------|
| API keys in `.env` (not hardcoded) | ✅ |
| `.env` in `.gitignore` | ✅ |
| No secrets in git history | ✅ |
| No database (no SQL injection risk) | ✅ |
| No user input (no XSS risk) | ✅ |
| External API calls: Groq + RSS only | ✅ |
| Local file system only (no server) | ✅ |

### 9.1 Secrets Management

- **Groq API Key:** Stored in `.env`, also in main app's `frontend/.env`
- **Regenerate:** https://console.groq.com/keys → Delete old key → Create new → Update `.env`

---

## 10. Operational Procedures

### 10.1 Daily Content Generation (30 seconds)

**Method A — Double-click:**
```
Double-click: C:\Users\DELL\.antigravity\StoryVocabs-social\RUN.bat
```

**Method B — PowerShell:**
```powershell
Right-click: generate.ps1 → "Run with PowerShell"
```

**Method C — Command line:**
```powershell
cd C:\Users\DELL\.antigravity\StoryVocabs-social
python generate.py
```

### 10.2 Posting Workflow

1. Script auto-opens Meta Business Suite
2. Caption is auto-copied to clipboard
3. Click "Create Post"
4. Paste caption (Ctrl+V)
5. Upload slides from `output/YYYY-MM-DD/`
6. Click Schedule or Publish

### 10.3 Manual Override

```powershell
# Use your own headline instead of auto-scraped news
python generate.py --manual "Your custom headline here"

# Generate story text only (no images)
python generate.py --story-only
```

### 10.4 Troubleshooting

| Issue | Fix |
|-------|-----|
| `GROQ_API_KEY not set` | Check `.env` has valid key |
| `Rate limit exceeded` | Wait until 6:00 AM Bangladesh time |
| `No module named 'groq'` | Run `pip install -r requirements.txt` |
| `Playwright not found` | Run `python -m playwright install chromium` |
| `JSON parse failed` | AI returned malformed JSON — retry |
| `No words loaded` | Check app path in `word_pack_manager.py` |

---

## 11. Monitoring & Quality

### 11.1 Quality Metrics

| Metric | Target | How to Check |
|--------|--------|-------------|
| Quality Score | ≥6.0/10 | Check console output |
| Word Count | 3-5 words | Check `content.json` |
| Story Length | 150-250 words | Check `content.json` |
| Slide Count | 3-4 slides | Check `output/YYYY-MM-DD/` |
| File Size | 600KB-1.6MB per slide | Check file sizes |

### 11.2 Content Quality Checklist

- [ ] Story covers the full news (not just headline)
- [ ] Words used naturally (not forced)
- [ ] Bangla translations are correct
- [ ] Logo visible on every slide
- [ ] CTA bar visible at bottom
- [ ] Text is readable (not too small)
- [ ] No empty slides

### 11.3 Tracking Files

| File | Purpose |
|------|---------|
| `story_usage_tracker.json` | Prevents repeating same news (6-month gap, max 2x/year) |
| `word_usage_tracker.json` | Prevents reusing same word >3 times/year |
| `output/YYYY-MM-DD/content.json` | Full content data for each day |

---

## 12. Backup & Disaster Recovery

### 12.1 What to Back Up

| Item | Location | Frequency |
|------|----------|-----------|
| `.env` file | Project root | Once (contains API key) |
| `config.py` | Project root | After any changes |
| Tracker files | `*.json` | Weekly |
| Output images | `output/` | After each generation |
| Templates | `templates/` | After any design changes |

### 12.2 Recovery Steps

| Scenario | Recovery |
|----------|----------|
| Groq API key lost | Regenerate at console.groq.com/keys |
| Project deleted | Clone from git or recreate from handover doc |
| Output lost | Re-run `python generate.py` (regenerates) |
| Templates corrupted | Restore from git history |
| Python broken | Reinstall Python + `pip install -r requirements.txt` |

### 12.3 Git Repository

```
Location: C:\Users\DELL\.antigravity\StoryVocabs-social\.git\
Remote: Not pushed (local only)
Recommendation: Push to GitHub for backup
```

---

## 13. Key Contacts

| Role | Contact | Notes |
|------|---------|-------|
| **Project Owner** | StoryVocabs Team | Decision maker for content strategy |
| **AI Engineer** | Previous developer | Built the pipeline |
| **Groq Support** | https://console.groq.com/ | API issues, rate limits |
| **Meta Support** | https://business.facebook.com/ | Posting issues |

---

## 14. Transition Plan

### Phase 1: Knowledge Transfer (Week 1)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Review this handover document | Successor |
| 2 | Run `python generate.py` and observe output | Successor |
| 3 | Post one piece of content manually | Successor |
| 4 | Review all source code files | Successor |
| 5 | Understand the genre schedule and tracking | Successor |

### Phase 2: Independent Operation (Week 2-3)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Generate content daily without assistance | Successor |
| 2 | Troubleshoot common issues independently | Successor |
| 3 | Modify templates if needed | Successor |
| 4 | Update genre schedule if needed | Successor |

### Phase 3: Full Handoff (Week 4)

| Step | Action | Owner |
|------|--------|-------|
| 1 | Previous developer available for questions only | Previous dev |
| 2 | Successor handles all operations | Successor |
| 3 | Push repo to GitHub for backup | Successor |
| 4 | Document any changes made | Successor |

---

## 15. Future Improvements

| Priority | Improvement | Effort |
|----------|-------------|--------|
| High | Push git repo to GitHub for backup | 10 min |
| High | Add more word packs to increase variety | 1 hour |
| Medium | Add Reel generation (video) | 2-3 hours |
| Medium | Auto-post via Meta Graph API | 3-4 hours |
| Medium | Add content calendar view | 2 hours |
| Low | Add analytics tracking | 4 hours |
| Low | Add multi-language support | 8 hours |

---

## 16. Quick Reference

### Daily Commands

```powershell
# Generate content
cd C:\Users\DELL\.antigravity\StoryVocabs-social
python generate.py

# Or just double-click RUN.bat
```

### Output Location

```
C:\Users\DELL\.antigravity\StoryVocabs-social\output\YYYY-MM-DD\
```

### Key Files to Know

| File | Purpose |
|------|---------|
| `RUN.bat` | Double-click to run |
| `generate.py` | Main pipeline script |
| `config.py` | All settings |
| `output/` | Generated slides |
| `.env` | API key |

### Emergency Contacts

- **Groq API down:** Wait for reset (6 AM BD time) or use `--manual` flag
- **Python broken:** Reinstall + `pip install -r requirements.txt`
- **Images not rendering:** `python -m playwright install chromium`

---

*End of Handover Document*
