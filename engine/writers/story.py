"""Writers for the two story pillars.

news_word : 3 exam words woven into today's Bangladesh news (1 story slide)
story60   : 5 exam words in a 60-second everyday Bangladeshi story (2 slides)

Both return a validated StoryPost whose Word cards are merged with the pack
data (pos, difficulty, example sentence) so nothing on the card is invented.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from engine import words as W
from engine.contracts import Category, StoryPost, StorySlide, Word
from engine.llm import call_json
from engine.voice import SYSTEM

CATEGORIES = {
    "cricket": Category(en="Sports", bn="খেলাধুলা", icon="🏏"),
    "sport": Category(en="Sports", bn="খেলাধুলা", icon="🏏"),
    "football": Category(en="Sports", bn="খেলাধুলা", icon="⚽"),
    "econom": Category(en="Economy", bn="অর্থনীতি", icon="📈"),
    "bank": Category(en="Banking", bn="ব্যাংকিং", icon="🏦"),
    "trade": Category(en="Business", bn="ব্যবসা", icon="💼"),
    "business": Category(en="Business", bn="ব্যবসা", icon="💼"),
    "tech": Category(en="Technology", bn="প্রযুক্তি", icon="💻"),
    "digital": Category(en="Technology", bn="প্রযুক্তি", icon="💻"),
    "startup": Category(en="Startups", bn="স্টার্টআপ", icon="🚀"),
    "election": Category(en="Politics", bn="রাজনীতি", icon="🗳️"),
    "politic": Category(en="Politics", bn="রাজনীতি", icon="🏛️"),
    "government": Category(en="Politics", bn="রাজনীতি", icon="🏛️"),
    "minister": Category(en="Politics", bn="রাজনীতি", icon="🏛️"),
    "india": Category(en="Geopolitics", bn="ভূ-রাজনীতি", icon="🌏"),
    "china": Category(en="Geopolitics", bn="ভূ-রাজনীতি", icon="🌏"),
    "foreign": Category(en="Geopolitics", bn="ভূ-রাজনীতি", icon="🌏"),
    "climate": Category(en="Environment", bn="পরিবেশ", icon="🌱"),
    "energy": Category(en="Energy", bn="জ্বালানি", icon="⚡"),
    "health": Category(en="Health", bn="স্বাস্থ্য", icon="🏥"),
    "education": Category(en="Education", bn="শিক্ষা", icon="🎓"),
    "university": Category(en="Education", bn="শিক্ষা", icon="🎓"),
    "student": Category(en="Education", bn="শিক্ষা", icon="🎓"),
    "history": Category(en="History", bn="ইতিহাস", icon="📜"),
}


def classify(text: str) -> Category:
    t = text.lower()
    for k, c in CATEGORIES.items():
        if k in t:
            return c
    return Category()


# ── LLM schemas (what the model returns; merged into contracts afterwards) ──
class _Pick(BaseModel):
    article_index: int = Field(..., ge=1)
    words: list[str] = Field(..., min_length=3, max_length=3)
    why: str = ""


class _WordOut(BaseModel):
    word: str
    phonetic: str = ""
    gloss_bn: str
    meaning_bn: str
    meaning_en: str
    example: str


class _StoryOut(BaseModel):
    headline_en: str
    headline_bn: str
    hero_word: str
    hero_gloss_bn: str
    story_slides: list[StorySlide]
    words: list[_WordOut]


PICK_PROMPT = """Pick ONE article and THREE words for today's post.

ARTICLES (choose the one a Dhaka student would actually stop scrolling for; skip crime/tragedy):
{articles}

CANDIDATE WORDS:
{words}

Rules: the three words must fit that article so naturally that a fluent journalist might use them — in the
sense the dictionary line gives, in a sentence that already exists in the story. Rejects: an adjective slapped on
an abstract noun to make it fit ("contrived solution", "credulous economy"), or a word whose sense has to be bent.
If fewer than three words fit an article honestly, choose another article. Prefer different parts of speech.
Return article_index (1-based), words (exact spellings), why (one clause per word: the sentence it lives in)."""

STORY_PROMPT = """Write the News Word post.

SOURCE ARTICLE
Title: {title}
Summary: {summary}

TARGET WORDS (use ALL, exactly once each, naturally):
{word_lines}

HOOK STYLE: {hook_instruction}

OUTPUT RULES
- headline_en: one English line (<= 11 words) about the news that contains exactly one target word,
  the hero word, wrapped as [[word]]. It must read like a real headline, not a vocabulary exercise.
- headline_bn: the same idea in natural Bangla, <= 12 words, no English except the hero word.
- hero_word / hero_gloss_bn: the hero word and a 1-3 word Bangla gloss.
- story_slides: exactly {n_slides} slide(s). section_label <= 3 words (e.g. "The story", "What happened", "Why it matters").
  paragraph: {words_per_slide} words of ENGLISH prose (this is English reading practice) at an exam-reading level,
  factual to the source, no invented numbers. Every target word appears inline as [[word|bangla gloss]] with a 1-3 word gloss.
  Do not start with "In a ..." or "Recently". Sound like a person, not a summary. Third person only — never invent
  a first-person scene, quote, or anecdote; every fact must come from the source.
- words: for each target word give phonetic (IPA between slashes, e.g. /ˈkændər/), gloss_bn (1-3 words), meaning_bn (one short natural
  Bangla sentence, <= 14 words), meaning_en (<= 16 words, plain), example (one NEW ENGLISH sentence about Bangladesh student life,
  the word wrapped in <b></b>). meaning_bn / meaning_en / gloss_bn MUST be faithful to the ENGLISH dictionary meaning
  given above — shorten it, never change it. The Bangla line above is a machine translation: reference only, never
  copy it. Write gloss_bn / meaning_bn the way a Dhaka student would SAY the meaning to a friend (spoken words such as
  বানানো, জোর করে মেলানো, ধাক্কা খেয়ে ফিরে আসা — not dictionary words such as কৃত্রিম, অপ্রাকৃতিক, পুনরুদ্ধার).
- The hero word (in headline_en) must be one of the target words, and its exact spelling must be used.
"""

STORY60_PROMPT = """Write the "Story in 60 seconds" post — a tiny, vivid, everyday Bangladeshi story.

SCENE: {topic}

TARGET WORDS (use ALL, exactly once each, naturally):
{word_lines}

HOOK STYLE: {hook_instruction}

OUTPUT RULES
- headline_en: the story's title line (<= 9 words) containing exactly one target word wrapped as [[word]] (the hero).
- headline_bn: the same title in natural Bangla (<= 10 words), hero word kept in English.
- hero_word / hero_gloss_bn.
- story_slides: exactly 2 slides, section_label <= 3 words ("Part 1", "Part 2" are fine),
  each paragraph 55-70 words of ENGLISH prose with concrete Bangladeshi detail (places, food, weather, money in taka).
  Every target word appears inline as [[word|bangla gloss]] (gloss 1-3 words). Real dialogue is welcome.
- words: phonetic (IPA between slashes), gloss_bn (1-3 words), meaning_bn (<= 14 words), meaning_en (<= 16 words), example (new ENGLISH sentence, word in <b></b>).
  Meanings must be faithful to the dictionary meanings given above — shorten, never change.
"""


def _word_lines(ws: list[dict]) -> str:
    return "\n".join(f"- {w['word']} ({w.get('pos','')}) — {w.get('bangla','')[:50]} — {w.get('meaning','')[:80]}" for w in ws)


def _merge_words(out: list[_WordOut], picked: list[dict]) -> list[Word]:
    by = {w["word"].lower(): w for w in picked}
    cards = []
    for o in out:
        src = by.get(o.word.strip().lower())
        if not src:
            src = W.by_name(o.word) or {"word": o.word, "bangla": o.meaning_bn, "meaning": o.meaning_en}
        cards.append(W.to_card(src, gloss_bn=o.gloss_bn, meaning_bn=o.meaning_bn, meaning_en=o.meaning_en,
                               example=o.example, phonetic=o.phonetic))
    return cards


def _ensure_marks(slides: list[StorySlide], words: list[Word]) -> list[StorySlide]:
    """If the model used a target word without [[word|gloss]] markup, add it (first occurrence)."""
    out = []
    marked = set()
    for s in slides:
        para = s.paragraph
        for w in words:
            if w.word.lower() in marked:
                continue
            if re.search(rf"\[\[{re.escape(w.word)}\w*\|", para, re.I):
                marked.add(w.word.lower())
                continue
            m = re.search(rf"(?<![\[\w])({re.escape(w.word)}\w*)(?![\w\]|])", para, re.I)
            if m:
                para = para[:m.start()] + f"[[{m.group(1)}|{w.gloss_bn}]]" + para[m.end():]
                marked.add(w.word.lower())
        out.append(StorySlide(section_label=s.section_label, paragraph=para))
    return out


def _assert_words_in_story(post: StoryPost) -> None:
    text = " ".join(s.paragraph for s in post.story_slides).lower()
    missing = [w.word for w in post.words if w.word.lower()[:5] not in text]
    if missing:
        raise ValueError(f"words missing from story: {missing}")


def write_news_word(date_str: str, articles: list[dict], strategy: dict, hook_style: str,
                    seed: int | None = None) -> StoryPost:
    cand = W.candidates(date_str, strategy, count=24, seed=seed)
    art_lines = "\n".join(f"{i}. [{a.get('source','')}] {a['title']} — {a['summary'][:220]}"
                          for i, a in enumerate(articles[:8], 1))
    pick = call_json(SYSTEM, PICK_PROMPT.format(articles=art_lines, words=W.candidate_lines(cand)), _Pick,
                     temperature=0.5, max_tokens=800)
    article = articles[min(pick.article_index, len(articles)) - 1]
    picked = [w for name in pick.words for w in cand if w["word"].lower() == name.strip().lower()]
    if len(picked) < 3:
        picked = (picked + [w for w in cand if w not in picked])[:3]

    hook_instr = strategy["hook_styles"].get(hook_style, {}).get("instruction", "")
    out = call_json(SYSTEM, STORY_PROMPT.format(
        title=article["title"], summary=article["summary"], word_lines=_word_lines(picked),
        hook_instruction=hook_instr, n_slides=1, words_per_slide="70-90"), _StoryOut, temperature=0.75, max_tokens=2500)

    cards = _merge_words(out.words, picked)
    post = StoryPost(
        pillar="news_word",
        headline_en=out.headline_en, headline_bn=out.headline_bn,
        hero_word=out.hero_word, hero_gloss_bn=out.hero_gloss_bn,
        story_slides=_ensure_marks(out.story_slides[:1], cards),
        words=cards,
        category=classify(article["title"] + " " + article["summary"]),
        source_title=article["title"], source_url=article.get("link", ""),
        topic=article["title"],
    )
    _assert_words_in_story(post)
    return post


def write_story60(date_str: str, strategy: dict, hook_style: str, seed: int | None = None) -> StoryPost:
    topics = strategy.get("story60_topics") or ["A BCS candidate the night before the exam"]
    idx = int(date_str.replace("-", "")) % len(topics)
    topic = topics[idx]
    cand = W.candidates(date_str, strategy, count=12, seed=seed)
    picked = cand[:5]
    hook_instr = strategy["hook_styles"].get(hook_style, {}).get("instruction", "")
    out = call_json(SYSTEM, STORY60_PROMPT.format(topic=topic, word_lines=_word_lines(picked),
                                                  hook_instruction=hook_instr), _StoryOut, temperature=0.85, max_tokens=3000)
    cards = _merge_words(out.words, picked)
    post = StoryPost(
        pillar="story60",
        headline_en=out.headline_en, headline_bn=out.headline_bn,
        hero_word=out.hero_word, hero_gloss_bn=out.hero_gloss_bn,
        story_slides=_ensure_marks(out.story_slides[:2], cards),
        words=cards,
        category=Category(en="Story", bn="গল্প", icon="📖"),
        topic=topic,
    )
    _assert_words_in_story(post)
    return post


def plain_story_text(post: StoryPost) -> str:
    """Story text with [[word|gloss]] markup reduced to plain words (for captions/critic)."""
    return " ".join(re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", s.paragraph) for s in post.story_slides)
