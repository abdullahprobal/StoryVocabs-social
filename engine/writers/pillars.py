"""Writers for the non-story pillars: quiz, confusables, in_app, offer."""
from __future__ import annotations

import json
import random

from pydantic import BaseModel, Field

from engine import settings
from engine import words as W
from engine.contracts import ConfusablesPost, InAppPost, OfferPost, QuizPost, Word
from engine.llm import call_json
from engine.voice import SYSTEM, product_facts

# ── quiz ───────────────────────────────────────────────────────────────────
class _QuizOut(BaseModel):
    phonetic: str = ""
    gloss_bn: str
    meaning_bn: str
    meaning_en: str
    example: str
    question_bn: str
    correct_option_bn: str
    distractors_bn: list[str] = Field(..., min_length=3, max_length=3)
    explanation_bn: str


QUIZ_PROMPT = """Make a one-image vocabulary quiz.

WORD: {word} ({pos}) — Bangla: {bangla} — English: {meaning}

Rules
- question_bn: one natural Bangla line asking what the word means (no "নিচের কোনটি" bureaucratic phrasing).
- correct_option_bn: the correct Bangla meaning in 1-4 words.
- distractors_bn: three WRONG Bangla options of the same length and register, each plausible for a student who
  half-remembers the word (near-miss meanings, or meanings of look-alike words). Never joke options.
- explanation_bn: <= 30 words explaining the meaning with a tiny memory hook.
- Also give phonetic (IPA between slashes, e.g. /rɪˈvɪər/), gloss_bn (1-3 words), meaning_bn (<= 14 words),
  meaning_en (<= 16 words), example (one ENGLISH sentence about Bangladeshi student life, word in <b></b>).
"""


def write_quiz(date_str: str, strategy: dict, seed: int | None = None) -> QuizPost:
    cand = W.candidates(date_str, strategy, count=8, seed=seed)
    w = cand[0]
    out = call_json(SYSTEM, QUIZ_PROMPT.format(word=w["word"], pos=w.get("pos", ""), bangla=w.get("bangla", ""),
                                               meaning=w.get("meaning", "")), _QuizOut, temperature=0.7, max_tokens=1200)
    rng = random.Random(seed if seed is not None else int(date_str.replace("-", "")))
    options = [out.correct_option_bn] + list(out.distractors_bn)
    rng.shuffle(options)
    card = W.to_card(w, gloss_bn=out.gloss_bn, meaning_bn=out.meaning_bn, meaning_en=out.meaning_en,
                     example=out.example, phonetic=out.phonetic)
    return QuizPost(word=card, question_bn=out.question_bn, options=options,
                    answer_index=options.index(out.correct_option_bn), explanation_bn=out.explanation_bn)


def quiz_answer_comment(post: QuizPost) -> str:
    letter = "ABCD"[post.answer_index]
    return (f"✅ সঠিক উত্তর: {letter}) {post.options[post.answer_index]}\n\n"
            f"{post.word.word} = {post.word.gloss_bn}\n{post.explanation_bn}\n\n"
            f"{settings.STRINGS.get('quiz_answer_outro', '')}")


# ── confusables ────────────────────────────────────────────────────────────
CONFUSABLES_FILE = settings.PROJECT_DIR / "data" / "confusables.json"


def confusable_pairs() -> list[dict]:
    """Owner-curated pairs. The LLM used to pick pairs and produced 'Enmity vs Enmity' and 'Incense vs Incent'."""
    try:
        pairs = json.loads(CONFUSABLES_FILE.read_text(encoding="utf-8")).get("pairs", [])
    except (OSError, ValueError):
        return []
    return [p for p in pairs if p.get("a") and p.get("b") and p["a"].strip().lower() != p["b"].strip().lower()]


def pick_pair(date_str: str, seed: int | None = None) -> dict:
    """Least-used curated pair (by the word tracker), ties broken by a date seed."""
    pairs = confusable_pairs()
    if not pairs:
        raise ValueError(f"no confusable pairs in {CONFUSABLES_FILE}")
    tracker = W.load_tracker()
    used = lambda w: sum(v for k, v in tracker.get(w.lower(), {}).items() if k != "dates")  # noqa: E731
    rng = random.Random(seed if seed is not None else int(date_str.replace("-", "")))
    rng.shuffle(pairs)
    return min(pairs, key=lambda p: used(p["a"]) + used(p["b"]))


class _WordOut(BaseModel):
    word: str
    phonetic: str = ""
    gloss_bn: str
    meaning_bn: str
    meaning_en: str
    example: str


class _ConfOut(BaseModel):
    title_bn: str
    a: _WordOut
    b: _WordOut
    difference_bn: str
    memory_tip_bn: str = ""


CONF_PROMPT = """Write the "confusables" post for {a} vs {b}.

THE VERIFIED DIFFERENCE (build everything on this; add no other claim): {rule}
Why students mix them up: {kind}

Known data
A: {a} ({a_pos}) — {a_bn} — {a_en}
B: {b} ({b_pos}) — {b_bn} — {b_en}

Rules
- English words are ALWAYS written in English letters. Never write an English word in Bangla script
  ("ইনসেন্স", "এনিমিটি" are wrong — write "incense", "enmity").
- title_bn: <= 10 words; a hook, not a label. It MUST contain both "{A}" and "{B}" in English letters,
  e.g. "{A} না {B} — কোনটা কখন?". No statistics, no "৯০% মানুষ".
- a / b: phonetic (IPA between slashes), gloss_bn (1-3 words), meaning_bn (<= 14 words), meaning_en (<= 16 words),
  example (one ENGLISH sentence each about Bangladeshi student life that makes the difference obvious; word in <b></b>).
- difference_bn: the one rule to remember, <= 40 words, in natural spoken Bangla.
- memory_tip_bn: leave "" unless the verified difference itself gives a real letter/sound cue
  (e.g. stationEry = Envelope, papEr). Never an "X = Y" equation you invented.
"""


def write_confusables(date_str: str, strategy: dict, seed: int | None = None) -> ConfusablesPost:
    pair = pick_pair(date_str, seed)
    a = W.by_name(pair["a"]) or {"word": pair["a"], "bangla": "", "meaning": ""}
    b = W.by_name(pair["b"]) or {"word": pair["b"], "bangla": "", "meaning": ""}
    A, B = a["word"].capitalize(), b["word"].capitalize()
    a = {**a, "word": A}
    b = {**b, "word": B}
    out = call_json(SYSTEM, CONF_PROMPT.format(
        A=A, B=B, rule=pair["rule"], kind=pair.get("kind", ""),
        a=A, a_pos=a.get("pos", ""), a_bn=a.get("bangla", "")[:80], a_en=a.get("meaning", "")[:120],
        b=B, b_pos=b.get("pos", ""), b_bn=b.get("bangla", "")[:80], b_en=b.get("meaning", "")[:120]),
        _ConfOut, temperature=0.7, max_tokens=1600)
    for w in (A, B):
        if w.lower() not in out.title_bn.lower():
            raise ValueError(f"confusables title must name both words in English letters: {out.title_bn!r}")
    ca = W.to_card(a, gloss_bn=out.a.gloss_bn, meaning_bn=out.a.meaning_bn, meaning_en=out.a.meaning_en,
                   example=out.a.example, phonetic=out.a.phonetic)
    cb = W.to_card(b, gloss_bn=out.b.gloss_bn, meaning_bn=out.b.meaning_bn, meaning_en=out.b.meaning_en,
                   example=out.b.example, phonetic=out.b.phonetic)
    return ConfusablesPost(title_bn=out.title_bn, pair=[ca, cb], difference_bn=out.difference_bn,
                           memory_tip_bn=out.memory_tip_bn)


# ── in_app ─────────────────────────────────────────────────────────────────
class _InAppOut(BaseModel):
    headline_bn: str
    feature_note_bn: str


IN_APP_PROMPT = """Write the on-image text for a product screenshot post.

SCREEN: {screen_name} — {screen_desc}
FACT LINE ALREADY ON THE IMAGE: {fact}

Rules
- headline_bn: <= 10 words, Bangla, about what the student can DO on this screen (benefit, not feature name).
- feature_note_bn: <= 20 words, one concrete detail from the screen description. No superlatives.
"""


def write_in_app(date_str: str, strategy: dict) -> InAppPost:
    screens = strategy.get("in_app_screens") or []
    if not screens:
        raise ValueError("strategy.in_app_screens is empty — add screenshots to render/assets/screens/")
    idx = int(date_str.replace("-", "")) % len(screens)
    s = screens[idx]
    facts = product_facts()["numbers"]
    fact_options = [f"{facts['word_packs']} word packs", f"{facts['words']:,} exam words", f"{facts['stories']} stories",
                    f"{facts['story_contexts_per_pack']} stories per pack", f"{facts['free_packs']} packs free"]
    fact = s.get("fact") or fact_options[idx % len(fact_options)]
    out = call_json(SYSTEM, IN_APP_PROMPT.format(screen_name=s["name"], screen_desc=s.get("desc", ""), fact=fact),
                    _InAppOut, temperature=0.6, max_tokens=500)
    return InAppPost(screenshot=s["file"], headline_bn=out.headline_bn, fact_line=fact, feature_note_bn=out.feature_note_bn)


# ── offer ──────────────────────────────────────────────────────────────────
class _OfferOut(BaseModel):
    headline_bn: str
    body_bn: str


OFFER_PROMPT = """Write a Friday-evening community/offer post of kind "{kind}".

{brief}

Rules
- headline_bn: <= 10 words, direct, no hype words ("সুবর্ণ সুযোগ", "ধামাকা" are banned).
- body_bn: <= 45 words, plain spoken Bangla, mention only the facts given above. No urgency lies ("শেষ সুযোগ").
"""

# Every brief must be true on the day it posts. Offers that are not live on storyvocabs.com stay out of
# strategy.json offer_rotation (the old referral / 20% student briefs described features that never existed).
OFFER_BRIEFS = {
    "free_path": "Fact: 3 word packs are completely free, no card needed, works on any phone browser. Goal: get a first try.",
    "pay_easy": "Fact: Pro is ৳300 for 1 month, ৳800 for 3 months, ৳1,500 for 6 months, ৳4,000 Lifetime. Pay with bKash, Nagad or Rocket through ZiniPay; Pro unlocks automatically. Goal: show paying is simple and safe.",
    "community": "Goal: ask the community a real question about how they revise vocabulary the week before an exam; promise to compile the best answers into next week's post.",
    "founder": "Goal: a two-line honest note from the founder about why StoryVocabs teaches words through stories (no claims, no research). Sign off as 'StoryVocabs team'.",
    # Switch on (add to offer_rotation) only after the offer is live on the site:
    "puja_offer": "Fact: Durga Puja offer, applied automatically (no code), until 21 October 2026 11:59 PM: Lifetime ৳2,000 (regular ৳4,000), 1 month ৳225 (৳300), 3 months ৳600 (৳800), 6 months ৳1,125 (৳1,500). Prices return to normal after that. Goal: festive, warm, no pressure lies.",
    "uni_trial": "Fact: sign up with a verified Bangladeshi university email and get 7 days of full Pro free. During the trial and for 24 hours after it, Lifetime is 50% off and the other plans 25% off, applied automatically. Goal: tell university students to try everything free.",
}

OFFER_DETAIL = {
    "free_path": "3 packs · ৳0",
    "pay_easy": "bKash · Nagad · Rocket",
    "community": "",
    "founder": "",
    "puja_offer": "Lifetime ৳2,000 · until 21 Oct",
    "uni_trial": "7 days free · uni email",
}


# Last date (inclusive, BST) a dated offer may be posted.
OFFER_UNTIL = {"puja_offer": "2026-10-21"}


def write_offer(date_str: str, strategy: dict) -> OfferPost:
    rotation = [k for k in (strategy.get("offer_rotation") or []) if k in OFFER_BRIEFS] or ["free_path", "pay_easy", "community", "founder"]
    from datetime import datetime
    # By day, not week: three offer evenings a week must not all repeat the same offer.
    kind = rotation[datetime.strptime(date_str, "%Y-%m-%d").toordinal() % len(rotation)]
    # While the Puja offer is live, a "pay easy" post quoting regular prices would contradict the site.
    if kind == "pay_easy" and date_str <= OFFER_UNTIL["puja_offer"]:
        kind = "puja_offer"
    # A dated offer never posts after it ends (e.g. puja_offer after 21 Oct): fall back to a standing offer.
    if OFFER_UNTIL.get(kind) and date_str > OFFER_UNTIL[kind]:
        kind = "uni_trial"
    out = call_json(SYSTEM, OFFER_PROMPT.format(kind=kind, brief=OFFER_BRIEFS[kind]), _OfferOut, temperature=0.7, max_tokens=600)
    return OfferPost(kind=kind, headline_bn=out.headline_bn, body_bn=out.body_bn, detail_line=OFFER_DETAIL.get(kind, ""))
