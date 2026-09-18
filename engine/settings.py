"""Single place for environment, paths and constants.

Everything that used to be scattered across config.py / image_renderer.py lives
here. Secrets come from the environment (GitHub Actions secrets or a local
.env); nothing secret is ever hard-coded.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR = ROOT / "data"
QUEUE_DIR = ROOT / "queue"
EVERGREEN_DIR = ROOT / "evergreen"
STATE_DIR = ROOT / "state"
ANALYTICS_DIR = ROOT / "analytics"
OUTPUT_DIR = ROOT / "output"          # rendered PNGs (git-ignored)
RENDER_DIR = ROOT / "render"
TEMPLATE_DIR = RENDER_DIR / "templates"
ASSET_DIR = RENDER_DIR / "assets"
STRATEGY_FILE = ROOT / "strategy.json"
PRODUCT_FACTS_FILE = DATA_DIR / "product_facts.json"
WORD_PACKS_FILE = DATA_DIR / "word_packs.json"
HOLIDAYS_FILE = DATA_DIR / "holidays.json"

for d in (QUEUE_DIR, EVERGREEN_DIR, STATE_DIR, ANALYTICS_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Brand / site ──────────────────────────────────────────────────────────
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "https://storyvocabs.bandb.academy").rstrip("/")
SITE_DISPLAY = PUBLIC_SITE_URL.replace("https://", "").replace("http://", "")
BRAND_NAME = "StoryVocabs"
FACEBOOK_PAGE_URL = os.getenv("FACEBOOK_PAGE_URL", "")

# ── Time ──────────────────────────────────────────────────────────────────
BST = timezone(timedelta(hours=6), name="BST")


def now_bst() -> datetime:
    return datetime.now(tz=BST)


def today_bst() -> str:
    return now_bst().strftime("%Y-%m-%d")


# ── Canvas ────────────────────────────────────────────────────────────────
CANVAS = (1080, 1350)       # 4:5 feed carousel
STORY_CANVAS = (1080, 1920)  # FB/IG Story
DEVICE_SCALE = 2

# ── Review / publish behaviour ────────────────────────────────────────────
# review   = Telegram preview, publish unless vetoed
# autopilot= publish without preview (still logs to Telegram)
# manual   = publish only after an explicit ✅
REVIEW_MODE = os.getenv("REVIEW_MODE", "review").lower()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
PUBLISH_TO_INSTAGRAM = os.getenv("PUBLISH_TO_INSTAGRAM", "true").lower() in ("1", "true", "yes")
PUBLISH_STORIES = os.getenv("PUBLISH_STORIES", "true").lower() in ("1", "true", "yes")

# ── LLM chain (all free tiers). First healthy provider wins. ─────────────
# Each entry: (provider, model). Override with LLM_CHAIN="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile"
_DEFAULT_CHAIN = [
    ("gemini", "gemini-2.5-flash"),
    ("gemini", "gemini-2.5-flash-lite"),
    ("groq", "qwen/qwen3.8-27b"),
    ("groq", "openai/gpt-oss-120b"),
    ("cerebras", "qwen-3-235b-a22b-instruct-2507"),
    ("cerebras", "gpt-oss-120b"),
    ("groq", "openai/gpt-oss-20b"),
    ("openrouter", "qwen/qwen3-next-80b-a3b-instruct:free"),
    ("openrouter", "google/gemma-3-27b-it:free"),
]


def llm_chain() -> list[tuple[str, str]]:
    raw = os.getenv("LLM_CHAIN")
    if not raw:
        return list(_DEFAULT_CHAIN)
    out = []
    for part in raw.split(","):
        if ":" in part:
            prov, model = part.strip().split(":", 1)
            out.append((prov.strip(), model.strip()))
    return out or list(_DEFAULT_CHAIN)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEYS = [v for k, v in sorted(os.environ.items()) if k.startswith("GROQ_API_KEY") and v]
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── Publishing credentials ────────────────────────────────────────────────
META_PAGE_ID = os.getenv("META_PAGE_ID", "")
META_PAGE_TOKEN = os.getenv("META_PAGE_TOKEN", "")
META_IG_USER_ID = os.getenv("META_IG_USER_ID", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Media host: "github" (public repo raw URLs) or "supabase" (storage bucket)
MEDIA_HOST = os.getenv("MEDIA_HOST", "github").lower()
MEDIA_REPO = os.getenv("MEDIA_REPO", "")           # e.g. abdullahprobal/storyvocabs-media
MEDIA_REPO_TOKEN = os.getenv("MEDIA_REPO_TOKEN", "")
MEDIA_REPO_BRANCH = os.getenv("MEDIA_REPO_BRANCH", "main")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "social")

# ── Content limits (enforced in gates.py) ─────────────────────────────────
HOOK_MAX_CHARS = 90
CAPTION_MAX_CHARS_FB = 1200
CAPTION_MAX_CHARS_IG = 1500
MAX_EMOJI = 4
HASHTAGS_FB = (2, 3)
HASHTAGS_IG = (5, 8)
QUALITY_PASS = 7.0
MAX_GENERATION_ATTEMPTS = 4
QUEUE_DAYS_AHEAD = int(os.getenv("QUEUE_DAYS_AHEAD", "2"))
