# Owner setup — the three credentials only you can create

Everything else (repos, deploy key, Groq keys, variables, workflows) is already configured.
Each step ends with pasting a value into **GitHub → StoryVocabs-social → Settings → Secrets and
variables → Actions → New repository secret**, or running `scripts/set_secrets.ps1` which prompts
for each value (input is hidden) and stores it with `gh`.

## 1. Telegram review bot (5 minutes)

1. Open Telegram → search **@BotFather** → `/newbot`
   - Name: `StoryVocabs Review`
   - Username: `storyvocabs_review_bot` (any free name ending in `bot`)
2. BotFather replies with a token like `123456789:AAF...` → secret **`TELEGRAM_BOT_TOKEN`**
3. Open your new bot's chat and send it any message (e.g. `hi`) — this lets it message you.
4. Get your chat id: open `https://api.telegram.org/bot<TOKEN>/getUpdates` in the browser and copy
   the number at `"chat":{"id": ... }` → secret **`TELEGRAM_CHAT_ID`**
   (or run `python scripts/telegram_chat_id.py` after putting the token in `.env`).

## 2. Gemini API key (free tier, best Bangla) (2 minutes)

1. https://aistudio.google.com/apikey → **Create API key** (any project)
2. Copy it → secret **`GEMINI_API_KEY`**

Groq keys are already set as fallback; Gemini simply becomes the first choice.

## 3. Meta (Facebook Page + Instagram) (15 minutes)

Prerequisites: a Facebook **Page** for StoryVocabs, and an **Instagram Business/Creator** account
connected to that Page (Page → Settings → Linked accounts → Instagram).

1. https://developers.facebook.com/apps → **Create app** → type *Business* → name `StoryVocabs Social`.
2. In the app: **Add product → Instagram** (Instagram Graph API) and note nothing else is required
   for your own Page while the app stays in *Development* mode.
3. https://developers.facebook.com/tools/explorer → select your app →
   **Permissions**: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `pages_read_user_content`, `read_insights`, `instagram_basic`, `instagram_content_publish`,
   `business_management` → **Generate Access Token** (log in, pick the Page + IG account).
4. Make it long-lived: **Access Token Tool** (https://developers.facebook.com/tools/accesstoken)
   → *Extend* the user token, or call
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`.
5. Get the **Page token** (never expires when derived from a long-lived user token):
   in the Explorer with the long-lived user token run `GET /me/accounts` → copy
   `id` → secret **`META_PAGE_ID`** and `access_token` → secret **`META_PAGE_TOKEN`**.
6. Instagram user id: `GET /{PAGE_ID}?fields=instagram_business_account` → the `id` inside →
   secret **`META_IG_USER_ID`** (skip if you launch Facebook-only; set variable
   `PUBLISH_TO_INSTAGRAM=false`).
7. Verify: `python scripts/check_meta.py` (uses `.env`) prints the Page name and token expiry.

## 4. First run

```
gh workflow run generate.yml -f dry_run=true          # renders + LLM only, nothing sent
gh workflow run generate.yml                           # real: uploads media + Telegram preview
gh workflow run publish.yml -f dry_run=true            # prints the Graph API calls it would make
gh workflow run publish.yml                            # publishes today's slot
```

Recommended first live target: an **unpublished** test Page (Page → Settings → Page visibility),
then switch the secrets to the real Page.

## 5. Later

* Add app screenshots to `render/assets/screens/` and list them in `strategy.json → in_app_screens`
  (`{"file": "flashcards.png", "name": "Flashcards", "desc": "...", "fact": "81 word packs"}`)
  to enable the Wednesday *In the app* pillar.
* Domain move: change variable `PUBLIC_SITE_URL` to `https://storyvocabs.com` and 301 the staging host.
* `REVIEW_MODE=autopilot` once you trust the output.
