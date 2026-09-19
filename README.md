# StoryVocabs Social Engine (v2)

Daily Facebook + Instagram content for StoryVocabs, generated, reviewed on Telegram and
published by GitHub Actions — at zero running cost (free LLM tiers, Meta Graph API, Telegram Bot API).

```
strategy.json ──► planner ──► writer (free LLM chain, JSON contract) ──► gates ──► render (Playwright)
                                   │                                                     │
                                   └──► caption (Bangla-first, clean tracked link) ◄──── critic ┘
                                                     │
              queue/<date>/<slot>.json  ◄────────────┘   (Telegram preview: ❌ skip · ✏️ note · ✅)
                                                     │
              publish.py at the slot ──► FB carousel + IG carousel + Stories + first comment
                                                     │
              insights.py weekly ──► analytics/ ──► re-weights pillars & hook styles ──► Telegram report
```

## Pillars (weekly calendar, `strategy.json`)

| Day | Pillar | Format |
|---|---|---|
| Sat | `news_word` — 3 exam words in today's Bangladesh news | 6-slide carousel |
| Sun | `quiz` — one word, 4 options; answer posted as a comment 6 h later | 1 image |
| Mon | `confusables` — two words students mix | 3-slide carousel |
| Tue | `news_word` (business/tech) | 6-slide carousel |
| Wed | `in_app` — real app screenshot + one honest number | 1 image (needs `render/assets/screens/`) |
| Thu | `story60` — 5 words in a 60-second Bangladeshi story | 8–9-slide carousel |
| Fri 20:00 | `offer` — free path / referral / student / community / founder | 1 image |

Every post also gets a 1080×1920 card for FB/IG Stories.

## Run locally

```bash
pip install -r requirements.txt && python -m playwright install chromium
cp .env.example .env            # fill keys
python scripts/sync_word_packs.py           # refresh data/word_packs.json from the app
python -m engine.generate --date 2026-09-20 --pillar quiz --dry-run   # renders to output/
python -m engine.publish --date 2026-09-20 --slot morning --dry-run    # prints the Graph API calls
python -m pytest -q tests
```

## Telegram review

Each generated post is sent to your Telegram chat (slides + a review card). Answer in plain words —
a reply to the card targets that card; a plain message targets the newest card still waiting:

* `approve` / `ok` / `✅` — approved; the bot confirms with the post day and time
* `skip` / `❌` — skipped; a ready-made backup post takes the slot
* `edit: <note>` / `✏️ <note>` — regenerated with your note; a new card arrives

`review.yml` reads your messages every 30 minutes and answers immediately; `publish.yml` re-checks at post
time and tells you if a slot was held because nothing was approved (`REVIEW_MODE=manual`). In
`REVIEW_MODE=review`, silence means publish; `autopilot` skips previews.

## Secrets & variables (GitHub → Settings → Secrets and variables → Actions)

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | free tier, best Bangla — primary writer (aistudio.google.com) |
| `GROQ_API_KEY_1..5` | free tier fallback (console.groq.com) |
| `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY` | optional further fallbacks |
| `META_PAGE_ID`, `META_PAGE_TOKEN`, `META_IG_USER_ID` | Facebook Page + linked Instagram Business account |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | review channel |
| `MEDIA_DEPLOY_KEY` | SSH private key registered as a write deploy key on the public media repo (set up automatically); `MEDIA_REPO_TOKEN` (PAT) is the alternative |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE` | only if `MEDIA_HOST=supabase` |

| Variable | Default |
|---|---|
| `MEDIA_HOST` | `github` (public repo raw URLs) or `supabase` |
| `MEDIA_REPO` | e.g. `abdullahprobal/storyvocabs-media` |
| `PUBLIC_SITE_URL` | `https://storyvocabs.com` (canonical production URL) |
| `REVIEW_MODE` | `review` / `autopilot` / `manual` |
| `PUBLISH_TO_INSTAGRAM`, `PUBLISH_STORIES` | `true` |

## Workflows

* `generate.yml` — 05:30 BST daily, fills today + tomorrow (`QUEUE_DAYS_AHEAD`), previews to Telegram
* `review.yml` — every 30 min: applies your Telegram decisions and replies
* `publish.yml` — 08:00 and 20:00 BST (slots), 14:00 BST (due quiz-answer comments)
* `weekly.yml` — Sunday 22:00 BST, Insights → weights → report
* `ci.yml` — tests on push

All state (`queue/`, `state/`, `analytics/`, `strategy.json`, `evergreen/`) is committed back by the bot.

Public captions show a clean first-party `/go/<pillar>/<post-id>` link. The
StoryVocabs app expands it to the full UTM URL, so attribution stays intact
without exposing a long query string. If the format changes, refresh existing
Telegram previews with `python scripts/refresh_telegram_previews.py`.

## Guard rails

* `data/product_facts.json` is the only source of product claims; `never_say` + regex claim patterns are enforced in `engine/gates.py`
* every story word must appear once with a Bangla gloss; captions carry exactly one tracked link
* critic pass (LLM) scores hook, Bangla and forced words; < 7 regenerates
* news scorer drops crime/tragedy stories; story tracker (6-month gap) and word tracker (≤ 3 uses/yr) prevent repeats
