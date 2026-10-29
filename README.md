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

## Project layer (`project/`) — everything brand-specific

| File | What it holds |
|---|---|
| `project/project.json` | brand name, wordmark, logo path, site URL, colours, audience, language rule, timezone, slots, UI strings, CTA options, vanity paths, news feeds |
| `project/voice.md` | the writing voice (system prompt) |
| `project/facts.json` | the only product claims allowed (+ `never_say`) |
| `project/pillars/<name>.json` | a content pillar as a prompt spec: layout (carousel / card / quiz), data source (dataset / news / none), prompt, slide/item counts, hook styles |
| `project/data/*.json` | datasets a pillar rotates through (each item needs an `id`) |

Built-in vocabulary pillars (`news_word`, `quiz`, `confusables`, `story60`, `in_app`, `offer`) stay available;
any other pillar name in `strategy.json → calendar` is looked up in `project/pillars/`. The engine code contains no brand strings.

## Pillars (weekly calendar, `strategy.json`): 3 posts a day

| Day | 08:00 | 13:00 | 20:00 |
|---|---|---|---|
| Sat | `news_word` (politics) | `quiz` | `offer` |
| Sun | `confusables` | `exam_tip` | `story60` |
| Mon | `quiz` | `confusables` | `proof` |
| Tue | `news_word` (business) | `quiz` | `offer` |
| Wed | `in_app` (→ `confusables` until screenshots exist) | `exam_tip` | `story60` |
| Thu | `confusables` | `quiz` | `offer` |
| Fri | `story60` | `quiz` | `proof` |

`exam_tip` and `proof` ("Inside StoryVocabs", only numbers from `project/facts.json`) are project pillars in
`project/pillars/`. Quiz answers are posted as a comment by about 21:30.

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

Every night at 21:00 BST the engine generates the whole next day and sends one numbered
**lineup** to Telegram (cards `#1`, `#2`… then a summary). You look once and answer once, or not at all:

* nothing — everything posts at its time (`REVIEW_MODE=review`)
* `skip 2` · `skip 1 and 3` · `skip all` — those don't post; a backup post takes the slot
* `approve all` · `1 ok, 2 skip` — explicit decisions per number
* `edit 2: shorter hook` — that post is regenerated with your note and a new card arrives
* replying directly to a card still targets that card

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

* `generate.yml` — 20:17 BST nightly: fills every missing/failed slot from now through 2 days ahead, tops the
  backup pool up to 6, sends one Telegram lineup; 10:17 BST repair run remakes anything still missing for today/tomorrow
* `review.yml` — every 30 min: applies your Telegram decisions and replies
* `publish.yml` — hourly heartbeat 08:23–22:23 BST: publishes whatever slot is due, plus due quiz-answer comments.
  If a slot's post failed and no backup is left, it writes a fresh quiz on the spot
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
