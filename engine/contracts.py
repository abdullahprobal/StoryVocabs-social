"""Pydantic contracts — the single source of truth for what the LLM must emit
and what the renderer/publisher consume. Every LLM output is parsed through
one of these; invalid output is rejected and regenerated.

Lengths are hard caps (see gates.py for the softer, semantic checks).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Pillar = str  # built-in: news_word, quiz, confusables, in_app, story60, offer — or any project/pillars/<name>.json
Slot = Literal["morning", "evening"]
Status = Literal["pending", "approved", "skipped", "published", "failed"]

_WS = re.compile(r"\s+")


def _clean(s: str) -> str:
    return _WS.sub(" ", (s or "").strip())


def _cap_words(s: str, n: int) -> str:
    parts = _clean(s).split(" ")
    return " ".join(parts[:n])


# ── Shared word card ───────────────────────────────────────────────────────
class Word(BaseModel):
    word: str
    pos: str = ""
    difficulty: Literal["Beginner", "Intermediate", "Advanced"] = "Intermediate"
    phonetic: str = ""
    gloss_bn: str = Field(..., description="1-3 Bangla words")
    meaning_bn: str = Field(..., description="<= 14 Bangla words, one sentence")
    meaning_en: str = Field(..., description="<= 16 English words, one sentence")
    example: str = Field("", description="One sentence, word wrapped in <b></b>")
    synonym: str = ""
    antonym: str = ""

    @field_validator("word")
    @classmethod
    def _word(cls, v):
        v = _clean(v)
        if not v:
            raise ValueError("empty word")
        return v[0].upper() + v[1:]

    @field_validator("pos")
    @classmethod
    def _pos(cls, v):
        return _clean(v).lower()[:12]

    @field_validator("gloss_bn")
    @classmethod
    def _gloss(cls, v):
        v = _cap_words(v, 3)
        if not v:
            raise ValueError("empty gloss_bn")
        return v

    @field_validator("meaning_bn")
    @classmethod
    def _mbn(cls, v):
        return _cap_words(v, 14)

    @field_validator("meaning_en")
    @classmethod
    def _men(cls, v):
        return _cap_words(v, 16)

    @field_validator("example")
    @classmethod
    def _ex(cls, v):
        v = _clean(v)[:160]
        # examples are English reading practice; a Bangla sentence here is a model slip
        if re.search(r"[ঀ-৿]", v):
            return ""
        return v

    @field_validator("synonym", "antonym")
    @classmethod
    def _syn(cls, v):
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        return _clean(v)[:60]


class StorySlide(BaseModel):
    section_label: str = Field(..., description="<= 3 words, shown uppercased")
    paragraph: str = Field(..., description="Vocab words inline as [[word|gloss_bn]]")

    @field_validator("section_label")
    @classmethod
    def _label(cls, v):
        return _cap_words(v, 3) or "The story"

    @field_validator("paragraph")
    @classmethod
    def _para(cls, v):
        v = _clean(v)
        if len(v.split()) < 15:
            raise ValueError("paragraph too short")
        return v


class Category(BaseModel):
    en: str = "Bangladesh"
    bn: str = "বাংলাদেশ"
    icon: str = "🇧🇩"


# ── Pillar payloads ────────────────────────────────────────────────────────
class StoryPost(BaseModel):
    """news_word (3 words, live news) and story60 (5 words, evergreen topic)."""

    pillar: Literal["news_word", "story60"] = "news_word"
    headline_en: str = Field(..., description="Hero word marked [[word]]")
    headline_bn: str = Field("", description="Short Bangla headline, <= 12 words")
    hero_word: str
    hero_gloss_bn: str
    story_slides: list[StorySlide] = Field(..., min_length=1, max_length=3)
    words: list[Word] = Field(..., min_length=2, max_length=5)
    category: Category = Category()
    source_title: str = ""
    source_url: str = ""
    topic: str = ""

    @field_validator("headline_en")
    @classmethod
    def _hl(cls, v):
        v = _clean(v)
        if "[[" not in v:
            raise ValueError("headline must mark the hero word with [[ ]]")
        return v[:120]

    @field_validator("headline_bn")
    @classmethod
    def _hbn(cls, v):
        v = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", v or "")
        return _cap_words(v, 14)

    @model_validator(mode="after")
    def _hero_in_words(self):
        names = {w.word.lower() for w in self.words}
        if self.hero_word.lower() not in names:
            raise ValueError("hero_word must be one of words[]")
        return self

    @property
    def word_count(self) -> int:
        return len(self.words)


class QuizPost(BaseModel):
    pillar: Literal["quiz"] = "quiz"
    word: Word
    question_bn: str = Field(..., description="One-line question, e.g. '\"Ubiquitous\" শব্দটির অর্থ কোনটি?'")
    options: list[str] = Field(..., min_length=4, max_length=4)
    answer_index: int = Field(..., ge=0, le=3)
    explanation_bn: str = Field(..., description="<= 30 words, why the answer is right")
    exam_tag: str = Field("BCS · Bank · Admission", description="Where this word appears")

    @field_validator("options")
    @classmethod
    def _opts(cls, v):
        v = [_clean(x)[:40] for x in v]
        if len({x.lower() for x in v}) != 4:
            raise ValueError("options must be distinct")
        return v

    @field_validator("explanation_bn")
    @classmethod
    def _expl(cls, v):
        return _cap_words(v, 30)


class ConfusablesPost(BaseModel):
    pillar: Literal["confusables"] = "confusables"
    title_bn: str = Field(..., description="<= 10 words, e.g. 'এই দুটি শব্দ ৯০% মানুষ গুলিয়ে ফেলে' is NOT allowed (no stats)")
    pair: list[Word] = Field(..., min_length=2, max_length=2)
    difference_bn: str = Field(..., description="<= 40 words, the one-line rule to remember")
    memory_tip_bn: str = Field("", description="<= 20 words mnemonic")

    @field_validator("title_bn")
    @classmethod
    def _t(cls, v):
        return _cap_words(v, 12)

    @field_validator("difference_bn")
    @classmethod
    def _d(cls, v):
        return _cap_words(v, 40)

    @field_validator("memory_tip_bn")
    @classmethod
    def _m(cls, v):
        return _cap_words(v, 22)


class InAppPost(BaseModel):
    pillar: Literal["in_app"] = "in_app"
    screenshot: str = Field(..., description="file name under render/assets/screens/")
    headline_bn: str = Field(..., description="<= 10 words")
    fact_line: str = Field(..., description="One honest number from product_facts")
    feature_note_bn: str = Field("", description="<= 20 words")

    @field_validator("headline_bn")
    @classmethod
    def _h(cls, v):
        return _cap_words(v, 12)


class OfferPost(BaseModel):
    pillar: Literal["offer"] = "offer"
    kind: Literal["referral", "student", "founder", "community", "free_path"]
    headline_bn: str = Field(..., description="<= 10 words")
    body_bn: str = Field(..., description="<= 45 words")
    detail_line: str = Field("", description="One line with the number, e.g. '৳150 – ৳500 per friend'")

    @field_validator("headline_bn")
    @classmethod
    def _h(cls, v):
        return _cap_words(v, 12)

    @field_validator("body_bn")
    @classmethod
    def _b(cls, v):
        return _cap_words(v, 48)


class ListItem(BaseModel):
    title: str
    sub: str = ""
    note: str = ""

    @field_validator("title")
    @classmethod
    def _t(cls, v):
        return _clean(v)[:60]

    @field_validator("sub", "note")
    @classmethod
    def _s(cls, v):
        return _clean(v)[:120]


class QuizBlock(BaseModel):
    question: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    answer_index: int = Field(..., ge=0, le=3)
    explanation: str = ""

    @field_validator("options")
    @classmethod
    def _o(cls, v):
        v = [_clean(x)[:40] for x in v]
        if len({x.lower() for x in v}) != 4:
            raise ValueError("options must be distinct")
        return v


class GenericPost(BaseModel):
    """Any project-defined pillar (project/pillars/<name>.json). Layout decides which fields render:
    carousel → headline/subtitle + slides + items recap · card → headline/body/detail · quiz → quiz block."""

    pillar: str
    layout: Literal["carousel", "card", "quiz"] = "carousel"
    kicker: str = ""
    headline: str = Field("", description="<= 11 words; may mark one phrase as [[phrase]]")
    subtitle: str = Field("", description="<= 14 words, second language or supporting line")
    slides: list[StorySlide] = Field(default_factory=list, max_length=4)
    items: list[ListItem] = Field(default_factory=list, max_length=6)
    body: str = Field("", description="card layout: <= 50 words")
    detail: str = Field("", description="card layout: one short line with the number/date")
    quiz: Optional[QuizBlock] = None
    source_title: str = ""
    source_url: str = ""
    item_id: str = ""

    @field_validator("headline", "subtitle", "kicker", "detail")
    @classmethod
    def _h(cls, v):
        return _clean(v)[:140]

    @field_validator("body")
    @classmethod
    def _b(cls, v):
        return _cap_words(v, 55)


# ── Caption ────────────────────────────────────────────────────────────────
class Caption(BaseModel):
    hook_line: str = Field(..., description="First line, <= 90 chars, Bangla-first")
    body: str = Field(..., description="2-5 short lines; blank line between ideas")
    comment_prompt: str = Field(..., description="One question that invites a comment")
    cta_line: str = Field(..., description="One CTA line without the URL; URL is appended by code")
    hashtags: list[str] = Field(default_factory=list)

    @field_validator("hook_line")
    @classmethod
    def _hook(cls, v):
        v = _clean(v)
        if not v:
            raise ValueError("empty hook")
        return v[:140]

    @field_validator("hashtags")
    @classmethod
    def _tags(cls, v):
        out = []
        for t in v:
            t = t.strip().lstrip("#").replace(" ", "")
            if t and t.lower() not in {x.lower() for x in out}:
                out.append(t)
        return out[:10]


class CriticVerdict(BaseModel):
    score: float = Field(..., ge=0, le=10)
    hook_score: float = Field(5, ge=0, le=10)
    bangla_ok: bool = True
    forced_words: list[str] = Field(default_factory=list)
    factual_error: bool = Field(False, description="true if any statement is untrue or misleading")
    issues: list[str] = Field(default_factory=list)
    improved_hook: str = ""


# ── Queue item (what generate.py writes and publish.py reads) ──────────────
class QueueItem(BaseModel):
    id: str
    date: str
    slot: Slot
    pillar: Pillar
    status: Status = "pending"
    hook_style: str = ""
    content: dict
    caption_fb: str = ""
    caption_ig: str = ""
    first_comment: str = ""            # posted as a comment after publish (quiz answer, etc.)
    comment_delay_minutes: int = 0
    media: list[str] = Field(default_factory=list)       # local PNG paths (relative to repo)
    media_urls: list[str] = Field(default_factory=list)  # public URLs once uploaded
    story_media: str = ""              # 1080x1920 PNG for FB/IG story
    story_media_url: str = ""
    quality_score: float = 0
    attempts: int = 0
    evergreen: bool = False
    telegram_message_id: Optional[int] = None
    fb_post_id: str = ""
    ig_media_id: str = ""
    fb_story_id: str = ""
    ig_story_id: str = ""
    review_note: str = ""
    error: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    published_at: str = ""
    utm_url: str = ""

    def slug(self) -> str:
        return f"{self.date}_{self.slot}_{self.pillar}"
