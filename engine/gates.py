"""Quality gates. Every function raises GateError with a human-readable reason,
or returns quietly. generate.py runs them all; a failure means regenerate
(up to settings.MAX_GENERATION_ATTEMPTS) and then a failed queue item.

Code gates (deterministic):
  banned_claims      – product_facts.never_say + a regex list of stat/research claims
  caption_shape      – hook length, one URL (FB) / zero (IG), emoji cap, hashtag range
  story_words        – every target word appears once in the story with a gloss
  render_check       – PNGs exist, right size, no unreplaced {{tokens}}

LLM gate:
  critic             – 1-10 score for hook/naturalness/Bangla; forced-word list
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

from engine import settings
from engine.contracts import CriticVerdict, StoryPost
from engine.llm import call_json
from engine.voice import SYSTEM, product_facts


class GateError(ValueError):
    pass


_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
_URL = re.compile(r"https?://\S+")
_STAT_CLAIMS = [
    r"\b\d{1,3}\s?%\s*(?:students|মানুষ|শিক্ষার্থী|people)",   # "90% students"
    r"\b\d+\s?(?:x|গুণ)\s*(?:বেশি|more|better|faster)",
    r"(?:গবেষণা|research|study|studies|scientist|বিজ্ঞানী)\w*\s+(?:বলছে|says|show|found|দেখ|প্রমাণ)",
    r"\b(?:#1|no\.?\s?1|number one|সেরা অ্যাপ|best app)\b",
    r"\b(?:guarantee|guaranteed|গ্যারান্টি|নিশ্চিত সাফল্য)\b",
]


def banned_claims(*texts: str) -> None:
    never = [s.lower() for s in product_facts().get("never_say", [])]
    blob = "\n".join(t or "" for t in texts)
    low = blob.lower()
    for phrase in never:
        if phrase and phrase in low:
            raise GateError(f"banned phrase: '{phrase}'")
    for pat in _STAT_CLAIMS:
        m = re.search(pat, blob, re.I)
        if m:
            raise GateError(f"unsupported claim: '{m.group(0)}'")


def caption_shape(fb: str, ig: str) -> None:
    hook = fb.split("\n", 1)[0]
    if len(hook) > settings.HOOK_MAX_CHARS + 10:
        raise GateError(f"hook too long ({len(hook)} chars): {hook[:60]}")
    if len(_URL.findall(fb)) != 1:
        raise GateError("facebook caption must contain exactly one URL")
    if _URL.search(ig):
        raise GateError("instagram caption must not contain a URL")
    if len(_EMOJI.findall(fb)) > settings.MAX_EMOJI + 2:
        raise GateError("too many emoji")
    if len(fb) > settings.CAPTION_MAX_CHARS_FB:
        raise GateError(f"facebook caption too long ({len(fb)})")
    if len(ig) > settings.CAPTION_MAX_CHARS_IG:
        raise GateError(f"instagram caption too long ({len(ig)})")
    ig_tags = re.findall(r"#[\wঀ-৿]+", ig)
    if not (settings.HASHTAGS_IG[0] <= len(ig_tags) <= settings.HASHTAGS_IG[1] + 2):
        raise GateError(f"instagram hashtag count {len(ig_tags)} out of range")
    if "vercel.app" in fb + ig:
        raise GateError("stale vercel link")


def story_words(post: StoryPost) -> None:
    text = " ".join(s.paragraph for s in post.story_slides)
    for w in post.words:
        marks = re.findall(rf"\[\[{re.escape(w.word)}\w*\|[^\]]+\]\]", text, re.I)
        if len(marks) == 0:
            raise GateError(f"'{w.word}' has no [[word|gloss]] mark in the story")
        if len(marks) > 2:
            raise GateError(f"'{w.word}' is marked {len(marks)} times (max 2)")
    if "[[" not in post.headline_en:
        raise GateError("headline has no hero mark")
    words_total = len(re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", text).split())
    cap = 140 if post.pillar == "news_word" else 170
    if words_total > cap:
        raise GateError(f"story too long: {words_total} words (cap {cap})")


def render_check(paths: list[str], size=settings.CANVAS) -> None:
    if not paths:
        raise GateError("no slides rendered")
    for p in paths:
        pth = Path(p)
        if not pth.exists() or pth.stat().st_size < 20_000:
            raise GateError(f"slide missing or tiny: {p}")
        with Image.open(pth) as im:
            w, h = im.size
        if (w, h) != (size[0] * settings.DEVICE_SCALE, size[1] * settings.DEVICE_SCALE) and (w, h) != size:
            raise GateError(f"slide {pth.name} is {w}x{h}, expected {size}")


def html_tokens(html: str, name: str = "") -> None:
    left = re.findall(r"\{\{[A-Z_]+\}\}", html)
    if left:
        raise GateError(f"unreplaced tokens in {name}: {sorted(set(left))[:5]}")


# ── LLM critic ─────────────────────────────────────────────────────────────
CRITIC_PROMPT = """You are the harshest editor at a Dhaka student media page. Rate this post 1-10.

Design notes (do NOT penalise these): the story text on the image is English on purpose (reading practice);
captions are Bangla-first on purpose; the link is a tracked website link and is required.

CAPTION (Facebook):
{caption}

ON-IMAGE TEXT:
{summary}

Score criteria (be strict; 8+ only if you would genuinely stop scrolling):
- hook_score: does line 1 make a tired student tap "See more"?
- Bangla: natural, current, no Sanskritised or machine-translated phrasing? (bangla_ok)
- Are any vocabulary words forced or wrongly used? (forced_words)
- Anything untrue, cringe, generic, or that sounds like an ad? (issues)
- improved_hook: rewrite line 1 to be better (<= 90 chars, Bangla-first), or "" if already strong.
Return score (overall), hook_score, bangla_ok, forced_words, issues, improved_hook."""


def critic(caption_fb: str, summary: str) -> CriticVerdict:
    caption_fb = _URL.sub("<link>", caption_fb)
    return call_json(SYSTEM, CRITIC_PROMPT.format(caption=caption_fb, summary=summary), CriticVerdict,
                     temperature=0.2, max_tokens=800)
