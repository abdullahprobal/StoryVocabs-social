"""Project-defined pillars: a JSON spec, no Python.

project/pillars/<name>.json
{
  "label": "Book of the day",                 # shown in Telegram cards
  "layout": "carousel" | "card" | "quiz",
  "source": "dataset" | "news" | "none",
  "dataset": "project/data/books.json",       # source=dataset: a JSON list of objects; each has an "id"
  "news_topic": "business",                   # source=news: a key of project.json → news.queries (or "general")
  "hook_styles": ["question", "bold_true"],   # subset of strategy.json hook_styles (optional)
  "prompt": "...{item}... {news_title} {news_summary} {hook_instruction} {facts}",   # the writer brief
  "slides": {"min": 1, "max": 2, "words": "60-90"},
  "items": {"min": 0, "max": 4},
  "first_comment": "",                        # optional; "{quiz_answer}" expands for quiz layouts
  "vanity_path": "books"                      # optional; else project.json vanity_paths[name] or the name
}

The prompt gets the whole GenericPost schema appended by call_json, so the model knows the
field names; the spec only has to say what a good post *is*. Dataset items are rotated
through state/dataset_usage.json so nothing repeats until the list is exhausted.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from engine import settings
from engine.contracts import GenericPost
from engine.llm import call_json
from engine.voice import SYSTEM, facts_block

USAGE = settings.STATE_DIR / "dataset_usage.json"


def specs() -> dict[str, dict]:
    out = {}
    if settings.PILLARS_DIR.exists():
        for f in sorted(settings.PILLARS_DIR.glob("*.json")):
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def spec_for(pillar: str) -> dict | None:
    return specs().get(pillar)


def _usage() -> dict:
    if USAGE.exists():
        try:
            return json.loads(USAGE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def pick_item(spec: dict, date_str: str, seed: int = 0) -> dict | None:
    path = settings.ROOT / spec.get("dataset", "")
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        return None
    used = set(_usage().get(str(path.relative_to(settings.ROOT)).replace("\\", "/"), []))
    fresh = [it for it in items if str(it.get("id", items.index(it))) not in used] or items
    rng = random.Random(int(date_str.replace("-", "")) * 7 + seed)
    return rng.choice(fresh)


def mark_item_used(spec: dict, item_id: str) -> None:
    if not item_id:
        return
    key = spec.get("dataset", "").replace("\\", "/")
    u = _usage()
    lst = u.setdefault(key, [])
    if item_id not in lst:
        lst.append(item_id)
    USAGE.write_text(json.dumps(u, indent=1, ensure_ascii=False), encoding="utf-8")


LAYOUT_RULES = {
    "carousel": ("Fill: kicker (<= 3 words), headline (<= 11 words, mark the key phrase as [[phrase]]), subtitle "
                 "(<= 14 words), slides[{{section_label, paragraph}}] ({slides_min}-{slides_max} slides, {words} words each), "
                 "items[{{title, sub, note}}] ({items_min}-{items_max} rows for the recap slide). Leave body/detail/quiz empty."),
    "card": ("Fill: kicker (<= 3 words), headline (<= 10 words), body (<= 50 words), detail (one short line with a "
             "number/date, or empty). Leave slides/items/quiz empty."),
    "quiz": ("Fill: headline = the thing being asked about (one or two words), quiz{{question, options (4, distinct, "
             "same length, near-miss distractors), answer_index, explanation (<= 30 words)}}. Leave slides/items empty. "
             "Never reveal the answer in headline or subtitle."),
}


def write_generic(pillar: str, date_str: str, strategy: dict, hook_style: str, seed: int = 0) -> GenericPost:
    spec = spec_for(pillar)
    if not spec:
        raise ValueError(f"no spec for pillar {pillar}")
    layout = spec.get("layout", "carousel")
    ctx = {
        "hook_instruction": strategy.get("hook_styles", {}).get(hook_style, {}).get("instruction", ""),
        "facts": facts_block(), "item": "", "item_id": "", "news_title": "", "news_summary": "", "news_url": "",
    }
    if spec.get("source") == "dataset":
        item = pick_item(spec, date_str, seed)
        if item is None:
            raise ValueError(f"dataset for {pillar} is empty or missing: {spec.get('dataset')}")
        ctx["item"] = json.dumps(item, ensure_ascii=False)
        ctx["item_id"] = str(item.get("id", ""))
    elif spec.get("source") == "news":
        from engine.news import news_pool
        pool = news_pool(date_str, spec.get("news_topic", "general"))
        if not pool:
            raise ValueError("no news available")
        a = pool[seed % len(pool)]
        ctx.update(news_title=a["title"], news_summary=a["summary"], news_url=a.get("link", ""))
    sl, it = spec.get("slides", {}), spec.get("items", {})
    rules = LAYOUT_RULES[layout].format(slides_min=sl.get("min", 1), slides_max=sl.get("max", 2), words=sl.get("words", "60-90"),
                                        items_min=it.get("min", 0), items_max=it.get("max", 4))
    lang = settings.LANGUAGE.get("caption_rule") or f"in {settings.LANGUAGE.get('primary', 'the audience language')}"
    user = (spec["prompt"].format(**ctx) + "\n\nOUTPUT RULES\n" + rules
            + f"\nLANGUAGE: write every text field {lang}, for this audience: {settings.AUDIENCE}."
            + f'\nSet pillar="{pillar}" and layout="{layout}".')
    post = call_json(SYSTEM, user, GenericPost, temperature=float(spec.get("temperature", 0.75)), max_tokens=2500)
    post.pillar, post.layout = pillar, layout
    post.item_id = ctx["item_id"]
    post.source_title, post.source_url = ctx["news_title"], ctx["news_url"]
    if layout == "carousel" and not post.slides:
        raise ValueError("carousel needs at least one slide")
    if layout == "quiz" and not post.quiz:
        raise ValueError("quiz layout needs a quiz block")
    if layout == "card" and not post.body:
        raise ValueError("card layout needs body text")
    return post


def first_comment(spec: dict, post: GenericPost) -> tuple[str, int]:
    tpl = spec.get("first_comment", "")
    if post.layout == "quiz" and post.quiz:
        letter = "ABCD"[post.quiz.answer_index]
        answer = f"✅ {letter}) {post.quiz.options[post.quiz.answer_index]}\n{post.quiz.explanation}".strip()
        return (tpl.replace("{quiz_answer}", answer) if tpl else answer), int(spec.get("comment_delay_minutes", 360))
    if tpl:
        return tpl.format(source_title=post.source_title, source_url=post.source_url), int(spec.get("comment_delay_minutes", 0))
    return "", 0


def summarize(post: GenericPost) -> str:
    parts = [f"Kicker: {post.kicker}", f"Headline: {post.headline}", f"Subtitle: {post.subtitle}"]
    if post.slides:
        parts.append("Slides: " + " | ".join(s.paragraph for s in post.slides))
    if post.items:
        parts.append("Recap rows: " + "; ".join(f"{i.title} — {i.sub}" for i in post.items))
    if post.body:
        parts.append(f"Body: {post.body} {post.detail}")
    if post.quiz:
        parts.append(f"Quiz: {post.quiz.question} options: {', '.join(post.quiz.options)} (answer is NOT on the image)")
    return "\n".join(parts)
