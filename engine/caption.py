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
from engine.gates import bookish_words
from engine.llm import call_json
from engine.voice import SYSTEM

CAPTION_PROMPT = """Write the caption for this post. It must read like a message from a senior student to a
junior — one real thing, said the way it would be said in a Messenger group. Not a lesson plan.

POST TYPE: {pillar}
CAPTION SHAPE: {shape}
WHAT THE IMAGE(S) SHOW:
{summary}

AUDIENCE: {audience} at {when}.

REGISTER ({caption_rule})
- If a Bangladeshi student would say it in English, keep it in English: exam, option, load shedding, plot twist,
  viva, deadline, screenshot. Never translate a loanword into a bookish noun (শক্তি ঘাটতি, প্রভাব ফেলে, অপ্রাকৃতিক).
- Bangla the way people type: short, spoken, no Sanskrit-flavoured words. "বানানো" not "কৃত্রিম"; "মানে" not "অর্থ হলো".
- English words are always typed in English letters, never spelled out in Bangla script ("incense", not "ইনসেন্স").
  Never talk about how a word is spelled in Bangla letters.
- One idea per line. Blank line between ideas. No labels ("Exam-এ:", "ট্রিক:", "Meaning:").

RULES
- hook_line: <= 90 characters. About the WORD or the moment, never a news headline or a year. No emoji at the start.
  Must earn the "See more" tap on its own. Never invent history, etymology, people, places or anecdotes.
- body: 2-4 short lines. ONE job: put the reader in a moment where they actually meet the word — an MCQ where
  three options look right, a viva answer, a movie plot, a friend's excuse — and show which sense wins.
  Say something true that is NOT already on the image. No hashtags. No URL.
  Memory tricks are banned unless they are a real synonym/antonym contrast from the image. Never write
  "X = Y" style equations or analogies you cannot defend.
- comment_prompt: one specific, low-effort question (one word or one sentence to answer).
- cta_line: pick ONE of these exactly, or a close variant with the same meaning:
  {cta_options}
  Never "download" (it is a website), never "unlimited", never a price unless the post is about pricing.
- hashtags: 6-8 tags without '#', relevant to the post and the audience (mix languages if the audience does).
{pillar_rules}
{examples}
"""

# One caption shape per hook style so the skeleton changes day to day.
SHAPES = {
    "question": "MCQ TRAP — open with the question a student actually gets wrong, then the one line that settles it.",
    "mistake": "CONFESSION — first person, one line: the mistake you (the senior) made with this word, then what fixed it.",
    "bold_true": "BEFORE / AFTER — the sentence a student writes before knowing the word, then the same sentence after.",
    "number": "MINI-SCENE — two lines of a real moment (exam hall, viva, group chat) where the word decides something.",
    "exam_angle": "MCQ TRAP — the two options that look right, and the one clue that picks the winner.",
    "story_open": "MINI-SCENE — two lines of a real moment where the word shows up naturally.",
}

PILLAR_RULES = {
    "quiz": ("QUIZ RULE: the answer is revealed in a comment later. The caption must NOT state, hint at, or narrow "
             "down the answer — no definition, no synonym, no example that reveals it. Build curiosity only."),
    "confusables": "Do not restate the rule that is already on the last slide; add the exam angle or a usage warning instead.",
    "news_word": ("NEWS RULE: the news is one clause of backdrop at most (\"আজকের load shedding-এর খবরে…\"). "
                  "The word is the post. Never open with the news, a year, or a statistic."),
}


def caption_examples() -> str:
    """Owner-curated example captions from project/voice.md (## Caption examples) — the few-shot voice anchor."""
    try:
        text = settings.VOICE_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""
    if "## Caption examples" not in text:
        return ""
    block = text.split("## Caption examples", 1)[1].split("\n## ", 1)[0].strip()
    return "\nEXAMPLES OF THE VOICE (match the register, never copy the lines):\n" + block if block else ""


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


def _never_write_block() -> str:
    """The owner's '## Never write' list, so the writer avoids it up front instead of burning retries on the gate."""
    words = bookish_words()
    return ("\nNEVER WRITE any of these (the post is rejected if one appears): " + ", ".join(words)) if words else ""


def write_caption(pillar: str, summary: str, hook_instruction: str, when: str = "8 am", layout: str = "",
                  hook_style: str = "", previous_error: str = "") -> Caption:
    rules = PILLAR_RULES.get(pillar, PILLAR_RULES.get(layout, ""))
    shape = SHAPES.get(hook_style, "") or hook_instruction
    prompt = CAPTION_PROMPT.format(
        pillar=pillar, shape=shape, summary=summary, when=when, pillar_rules=rules, examples=caption_examples(),
        audience=settings.AUDIENCE or "the brand's followers",
        caption_rule=settings.LANGUAGE.get("caption_rule") or "in the brand voice",
        cta_options=" / ".join(f'"{o}"' for o in settings.CTA_OPTIONS) or "a one-line invitation to visit the site",
    ) + _never_write_block()
    if previous_error:
        prompt += f"\nYOUR PREVIOUS DRAFT WAS REJECTED: {previous_error[:300]}\nFix exactly that this time."
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
