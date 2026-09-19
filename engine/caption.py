"""Caption engine: brief → LLM caption → FB / IG variants with one UTM link.

The LLM never writes the URL or the hashtags' final selection; code appends
them so every post carries exactly one tracked link and a sane tag set.
"""
from __future__ import annotations

import random
import re
from urllib.parse import urlencode

from engine import settings
from engine.contracts import Caption
from engine.llm import call_json
from engine.voice import SYSTEM

CAPTION_PROMPT = """Write the caption for this post.

POST TYPE: {pillar}
HOOK STYLE: {hook_instruction}
WHAT THE IMAGE(S) SHOW:
{summary}

AUDIENCE: {audience} at {when}.

RULES
- hook_line: the first line, <= 90 characters, {caption_rule}.
  It must earn the "See more" tap on its own. No emoji at the start. No "আজকের শব্দ" style labels.
  The hook must be about what is on the image. Never invent history, etymology, people, places or anecdotes
  about a word ("এই শব্দটা এসেছে..." is banned unless the origin is on the image).
- body: 2-5 short lines separated by blank lines. Say something true and useful that is NOT already on the image
  (context, the exam angle, a usage warning, a one-line memory trick). No hashtags here. No URL here.
- comment_prompt: one specific question that makes it easy to reply with one word or a sentence
  (e.g. "এই শব্দটা দিয়ে একটা বাক্য লিখো তো — সবচেয়ে ভালোটা পিন করব")
- cta_line: pick ONE of these exactly, or a close variant with the same meaning:
  {cta_options}
  Never "download" (it is a website), never "unlimited", never a price unless the post is about pricing.
- hashtags: 6-8 tags without '#', relevant to the post and the audience (mix languages if the audience does).
{pillar_rules}
"""

PILLAR_RULES = {
    "quiz": ("QUIZ RULE: the answer is revealed in a comment later. The caption must NOT state, hint at, or narrow "
             "down the answer — no definition, no synonym, no example that reveals it. Build curiosity only."),
    "confusables": "Do not restate the rule that is already on the last slide; add the exam angle or a usage warning instead.",
    "news_word": "Reference the news event in line 1 or 2 so the post reads as today's news, not a word list.",
}


def build_utm(pillar: str, post_id: str, source: str = "facebook") -> str:
    tag = post_id[4:8] if len(post_id) >= 8 and post_id[:8].isdigit() else post_id
    q = urlencode({"utm_source": source, "utm_medium": "social", "utm_campaign": pillar, "utm_content": tag})
    return f"{settings.PUBLIC_SITE_URL}/?{q}"


def build_display_url(pillar: str, post_id: str) -> str:
    """The link readers see: `storyvocabs.com/quiz/0920` — bare domain, human path,
    a 4-digit day tag for per-post attribution. The app 302s it to the UTM landing
    URL, so tracking survives without a machine id in public."""
    tag = post_id[4:8] if len(post_id) >= 8 and post_id[:8].isdigit() else ""
    path = settings.PILLAR_PATHS.get(pillar, pillar)
    if not path:
        return settings.SITE_DISPLAY
    return f"{settings.SITE_DISPLAY}/{path}" + (f"/{tag}" if tag else "")


def write_caption(pillar: str, summary: str, hook_instruction: str, when: str = "8 am", layout: str = "") -> Caption:
    rules = PILLAR_RULES.get(pillar, PILLAR_RULES.get(layout, ""))
    prompt = CAPTION_PROMPT.format(
        pillar=pillar, hook_instruction=hook_instruction, summary=summary, when=when, pillar_rules=rules,
        audience=settings.AUDIENCE or "the brand's followers",
        caption_rule=settings.LANGUAGE.get("caption_rule") or "in the brand voice",
        cta_options=" / ".join(f'"{o}"' for o in settings.CTA_OPTIONS) or "a one-line invitation to visit the site",
    )
    return call_json(SYSTEM, prompt, Caption, temperature=0.8, max_tokens=1200)


def _tags(cap: Caption, strategy: dict, lo: int, hi: int, rng: random.Random) -> list[str]:
    core = list(strategy.get("hashtags", {}).get("core", []))
    pool = list(strategy.get("hashtags", {}).get("pool", []))
    chosen: list[str] = []
    for t in core + cap.hashtags + pool:
        t = t.strip().lstrip("#").replace(" ", "")
        if t and t.lower() not in {c.lower() for c in chosen} and re.match(r"^[\wঀ-৿]+$", t):
            chosen.append(t)
    keep = chosen[: max(lo, min(hi, len(chosen)))]
    return keep


def assemble(cap: Caption, pillar: str, post_id: str, strategy: dict, seed: int = 0) -> tuple[str, str, str]:
    """Return (facebook_caption, instagram_caption, utm_url)."""
    rng = random.Random(seed)
    url_fb = build_utm(pillar, post_id, "facebook")
    display_url = build_display_url(pillar, post_id)
    body = cap.body.strip()
    fb_tags = " ".join("#" + t for t in _tags(cap, strategy, *settings.HASHTAGS_FB, rng))
    ig_tags = " ".join("#" + t for t in _tags(cap, strategy, *settings.HASHTAGS_IG, rng))

    fb = f"{cap.hook_line.strip()}\n\n{body}\n\n{cap.comment_prompt.strip()}\n\n{cap.cta_line.strip()}\n{display_url}\n\n{fb_tags}"
    ig = f"{cap.hook_line.strip()}\n\n{body}\n\n{cap.comment_prompt.strip()}\n\n{cap.cta_line.strip()} — link in bio\n.\n.\n{ig_tags}"
    return fb.strip(), ig.strip(), url_fb
