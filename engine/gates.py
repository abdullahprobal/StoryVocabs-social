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
# Public captions use the bare vanity link (storyvocabs.com/quiz) — count those too.
_SITE_LINK = re.compile(r"(?<![\w/])" + re.escape(settings.SITE_DISPLAY) + r"(?:/[\w-]+){0,2}(?![\w/])")
_STAT_CLAIMS = [
    r"\b\d{1,3}\s?%\s*(?:students|মানুষ|শিক্ষার্থী|people)",   # "90% students"
    r"\b\d+\s?(?:x|গুণ)\s*(?:বেশি|more|better|faster)",
    r"(?:গবেষণা|research|study|studies|scientist|বিজ্ঞানী)\w*\s+(?:বলছে|says|show|found|দেখ|প্রমাণ)",
    r"\b(?:#1|no\.?\s?1|number one|সেরা অ্যাপ|best app)\b",
    r"\b(?:guarantee|guaranteed|গ্যারান্টি|নিশ্চিত সাফল্য)\b",
]


def banned_claims(*texts: str, allow_percent: bool = False) -> None:
    """Raise on any never_say phrase, any research/statistic pattern and — unless allow_percent
    (the student-discount offer post) — any percentage at all."""
    never = [s.lower() for s in product_facts().get("never_say", [])]
    blob = "\n".join(t or "" for t in texts)
    low = blob.lower()
    if not allow_percent and re.search(r"[\d০-৯]\s?%", blob):
        raise GateError("percentage claim in copy")
    for phrase in never:
        if phrase and phrase in low:
            raise GateError(f"banned phrase: '{phrase}'")
    for pat in _STAT_CLAIMS:
        m = re.search(pat, blob, re.I)
        if m:
            raise GateError(f"unsupported claim: '{m.group(0)}'")


# Any script: "Contrived = Created" and "‘স’ = ধূপ" are the same invented-mnemonic smell.
_EQUATION = re.compile(r"[\wঀ-৿\'‘’\"“”][\'‘’\"“”]?\s*=\s*[\'‘’\"“”]?[\wঀ-৿]")
_TRICK_LABEL = re.compile(r"(মনে রাখার ট্রিক|ট্রিক\s*:|memory trick|mnemonic)", re.I)


def bookish_words() -> list[str]:
    """Tokens a Dhaka student would never type, curated by the owner in project/voice.md
    under '## Never write' (one per line, '- ' prefix). Empty list if the section is absent."""
    try:
        text = settings.VOICE_FILE.read_text(encoding="utf-8")
    except OSError:
        return []
    if "## Never write" not in text:
        return []
    block = text.split("## Never write", 1)[1].split("\n## ", 1)[0]
    return [ln[2:].strip() for ln in block.splitlines() if ln.startswith("- ") and ln[2:].strip()]


def register(fb: str) -> None:
    """Spoken-Banglish gate: reject bookish tokens and invented 'X = Y' mnemonics.
    Both were what made the 2026-09-19 'contrived' caption feel machine-written."""
    body = _SITE_LINK.sub("", _URL.sub("", fb))
    for w in bookish_words():
        if w and w in body:
            raise GateError(f"bookish word '{w}' — rewrite in spoken Banglish")
    if _TRICK_LABEL.search(body):
        raise GateError("labelled memory trick — say it plainly or drop it")
    if _EQUATION.search(body):
        raise GateError("'X = Y' style mnemonic/equation — banned unless a real contrast on the image")


def headwords_in_english(fb: str, words: list[str]) -> None:
    """A confusables caption must name both words in English letters — 'ইনসেন্স নাকি ইনসেন্ট' reads as noise."""
    body = fb.lower()
    missing = [w for w in words if not re.search(rf"\b{re.escape(w.lower())}\b", body)]
    if missing:
        raise GateError(f"caption must write {missing} in English letters")


def caption_shape(fb: str, ig: str) -> None:
    hook = fb.split("\n", 1)[0]
    if len(hook) > settings.HOOK_MAX_CHARS + 10:
        raise GateError(f"hook too long ({len(hook)} chars): {hook[:60]}")
    if len(_URL.findall(fb)) + len(_SITE_LINK.findall(fb)) != 1:
        raise GateError("facebook caption must contain exactly one link")
    if _URL.search(fb):
        raise GateError("facebook caption must show the bare vanity link, not a full URL")
    if _URL.search(ig) or _SITE_LINK.search(ig):
        raise GateError("instagram caption must not contain a link")
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


_DEFINES = re.compile(r"(মানে হলো|মানে হচ্ছে|অর্থ হলো|অর্থ হচ্ছে|\bmeans\b|meaning is|refers to|বোঝায়)", re.I)


def quiz_caption_keeps_answer(fb: str, correct_option: str, gloss: str) -> None:
    """A quiz caption must not contain the correct option, the gloss, or a definition-shaped hook."""
    low = fb.lower()
    for leak in (correct_option, gloss):
        leak = (leak or "").strip().lower()
        if len(leak) >= 3 and leak in low:
            raise GateError(f"quiz caption leaks the answer: '{leak}'")
    hook = fb.split("\n", 1)[0]
    if _DEFINES.search(hook):
        raise GateError("quiz hook defines the word")


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
captions are Banglish on purpose (English loanwords stay English); the final CTA line and the link are a fixed
brand requirement — never call them promotional or ad-like, judge everything above them.

CAPTION (Facebook):
{caption}

ON-IMAGE TEXT:
{summary}

Score criteria (be strict; 8+ only if you would genuinely stop scrolling and believe a person typed it):
- hook_score: does line 1 make a tired student tap "See more"? A news headline, a year or a statistic as line 1 scores <= 4.
- bangla_ok: would every line look normal in a WhatsApp/Messenger group of Dhaka students? Set false for
  translationese (English sentence shapes: "X শুধুই Y নয়, Z-ও", "যেন কোনো", "প্রভাব ফেলে"), Sanskrit-flavoured
  nouns (শক্তি ঘাটতি, অপ্রাকৃতিক, কৃত্রিম where a student says বানানো), or a translated loanword (load shedding → শক্তি ঘাটতি).
- forced_words: vocabulary words jammed onto abstract nouns ("Contrived সমাধান") or used in the wrong sense.
- factual_error: true if ANY statement about the news, the exam, or the word is untrue or misleading — a wrong
  or flattened meaning counts, and so does an INVENTED memory trick, analogy or etymology ("Contrived = Created").
- Read it as a sharp student who is deciding whether this page is worth following. Any line that makes no
  literal sense ("শব্দের শেষে -ity, শত্রুত্বের মতোই শেষ"), a pair of identical or non-existent words, a claim
  about Bangla spelling of an English word, or an English word written in Bangla script = score <= 4 and
  factual_error true. Generic filler ("ভুল করলে পয়েন্ট হারাতে পারো") caps the score at 6.
- issues: anything cringe, generic, label-like ("Exam-এ:", "ট্রিক:"), or that reads as a template.
- improved_hook: rewrite line 1 to be better (<= 90 chars, about the word, spoken), or "" if already strong.
Return score (overall), hook_score, bangla_ok, forced_words, factual_error, issues, improved_hook."""


def critic(caption_fb: str, summary: str, avoid: str | None = None) -> CriticVerdict:
    """Second opinion. `avoid` is the writer's "provider:model" so the critic prefers a
    different model — a model grading its own dialect passes translationese."""
    caption_fb = _SITE_LINK.sub("<link>", _URL.sub("<link>", caption_fb))
    return call_json(SYSTEM, CRITIC_PROMPT.format(caption=caption_fb, summary=summary), CriticVerdict,
                     temperature=0.2, max_tokens=800, avoid=avoid, strong=True)
