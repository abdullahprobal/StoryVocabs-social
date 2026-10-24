"""Generate queue items: plan → write → caption → gates → render → (upload) → Telegram preview.

    python -m engine.generate                      # today + QUEUE_DAYS_AHEAD
    python -m engine.generate --date 2026-09-20    # one date
    python -m engine.generate --pillar quiz        # force a pillar for the date's slot
    python -m engine.generate --evergreen 10       # fill the evergreen fallback pool
    python -m engine.generate --dry-run            # no upload, no Telegram, no trackers

Exit code is 0 when every planned slot has a usable queue item, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from engine import gates, llm, settings
from engine import words as W
from engine.caption import assemble, write_caption
from engine.contracts import ConfusablesPost, GenericPost, InAppPost, OfferPost, QueueItem, QuizPost, StoryPost
from engine.llm import LLMError
from engine.planner import PlanItem, load_strategy, plan_for_date, slot_datetime_bst
from engine.writers import pillars as P
from engine.writers import story as S
from engine.writers import generic as G
from render import image_renderer as R


def log(msg: str) -> None:
    print(msg, flush=True)


def queue_path(date_str: str, slot: str) -> Path:
    return settings.QUEUE_DIR / date_str / f"{slot}.json"


def load_item(path: Path) -> QueueItem | None:
    if not path.exists():
        return None
    try:
        return QueueItem.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def save_item(item: QueueItem, path: Path | None = None) -> Path:
    path = path or queue_path(item.date, item.slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(item.model_dump_json(indent=1), encoding="utf-8")
    return path


# ── per-pillar content + summary ───────────────────────────────────────────
def summarize(content) -> str:
    """Plain-text description of what the images show (for the caption writer and critic)."""
    if isinstance(content, StoryPost):
        words = "; ".join(f"{w.word} = {w.gloss_bn}" for w in content.words)
        return (f"Cover headline: {re.sub(r'[\\[\\]]', '', content.headline_en)} / {content.headline_bn}\n"
                f"Story: {S.plain_story_text(content)}\nWords: {words}\n"
                f"Source: {content.source_title or content.topic}")
    if isinstance(content, QuizPost):
        return (f"Quiz image: word '{content.word.word}' ({content.word.pos}); question: {content.question_bn}; "
                f"options: {', '.join(content.options)}. The answer is NOT on the image (it is posted as a comment later).")
    if isinstance(content, ConfusablesPost):
        a, b = content.pair
        return (f"Confusables carousel: {a.word} ({a.gloss_bn}) vs {b.word} ({b.gloss_bn}). Title: {content.title_bn}. "
                f"Rule: {content.difference_bn}. Tip: {content.memory_tip_bn}")
    if isinstance(content, InAppPost):
        return f"App screenshot post. Headline: {content.headline_bn}. Fact: {content.fact_line}. Note: {content.feature_note_bn}"
    if isinstance(content, OfferPost):
        return f"Offer/community image ({content.kind}). Headline: {content.headline_bn}. Body: {content.body_bn}. Detail: {content.detail_line}"
    if isinstance(content, GenericPost):
        return G.summarize(content)
    return str(content)


def make_content(plan: PlanItem, strategy: dict, attempt: int, previous_error: str = ""):
    seed = int(plan.date.replace("-", "")) * 10 + attempt
    if previous_error:
        # Story and generic writers read the hook instruction: tell them why the last draft was rejected.
        hooks = dict(strategy.get("hook_styles", {}))
        base = hooks.get(plan.hook_style, {}).get("instruction", "")
        hooks[plan.hook_style] = {"instruction": f"{base}\nYOUR PREVIOUS DRAFT WAS REJECTED: {previous_error[:300]}\nFix exactly that."}
        strategy = {**strategy, "hook_styles": hooks}
    if G.spec_for(plan.pillar):
        return G.write_generic(plan.pillar, plan.date, strategy, plan.hook_style, seed=seed)
    if plan.pillar == "news_word":
        from engine.news import news_pool
        arts = news_pool(plan.date, plan.topic_group or "general")
        if not arts:
            raise ValueError("no news articles available")
        return S.write_news_word(plan.date, arts, strategy, plan.hook_style, seed=seed)
    if plan.pillar == "story60":
        return S.write_story60(plan.date, strategy, plan.hook_style, seed=seed)
    if plan.pillar == "quiz":
        return P.write_quiz(plan.date, strategy, seed=seed)
    if plan.pillar == "confusables":
        return P.write_confusables(plan.date, strategy, seed=seed)
    if plan.pillar == "in_app":
        return P.write_in_app(plan.date, strategy)
    if plan.pillar == "offer":
        return P.write_offer(plan.date, strategy)
    raise ValueError(f"unknown pillar {plan.pillar}")


def render_content(content, out_dir: Path, date_str: str) -> tuple[list[str], str]:
    """Returns (carousel paths, story-card path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    if isinstance(content, StoryPost):
        paths = R.render_story_post(content, out_dir, date_str)
        story = R.render_story_card(R.mark_hero(content.headline_en), content.headline_bn,
                                    settings.STRINGS.get("story_kicker", "") if content.pillar == "news_word" else settings.STRINGS.get("story60_kicker", ""), out_dir)
    elif isinstance(content, QuizPost):
        paths = R.render_quiz(content, out_dir)
        story = R.render_story_card(f'<span class="mark">{R.esc(content.word.word)}</span> মানে কী?',
                                    content.question_bn, settings.STRINGS.get("quiz_kicker", "Quiz"), out_dir)
    elif isinstance(content, ConfusablesPost):
        paths = R.render_confusables(content, out_dir)
        a, b = content.pair
        story = R.render_story_card(f'{R.esc(a.word)} <i>vs</i> {R.esc(b.word)}', content.title_bn, settings.STRINGS.get("confusables_kicker", ""), out_dir)
    elif isinstance(content, InAppPost):
        paths = R.render_in_app(content, out_dir)
        story = R.render_story_card(R.esc(content.fact_line), content.headline_bn, settings.STRINGS.get("in_app_kicker", ""), out_dir)
    elif isinstance(content, GenericPost):
        from render.generic import render_generic
        spec = G.spec_for(content.pillar) or {}
        paths = render_generic(content, out_dir, date_str, spec.get("label", content.pillar))
        story = R.render_story_card(R.mark_hero(content.headline) if content.headline else R.esc(spec.get("label", "")),
                                    content.subtitle or content.body[:120], content.kicker or spec.get("label", ""), out_dir)
    elif isinstance(content, OfferPost):
        paths = R.render_offer(content, out_dir)
        story = R.render_story_card(R.esc(content.detail_line or content.headline_bn), content.body_bn[:120], settings.BRAND_NAME, out_dir)
    else:
        raise ValueError("unknown content type")
    return paths, story


CONTENT_TYPES = {"news_word": StoryPost, "story60": StoryPost, "quiz": QuizPost,
                 "confusables": ConfusablesPost, "in_app": InAppPost, "offer": OfferPost}


def content_model(item: QueueItem):
    """Rebuild the pydantic content object stored in a queue item."""
    if G.spec_for(item.pillar) or item.content.get("layout"):
        return GenericPost.model_validate(item.content)
    return CONTENT_TYPES.get(item.pillar, GenericPost).model_validate(item.content)


def rerender(item: QueueItem) -> QueueItem:
    """Re-render slides for an item whose PNGs are not on this machine (other runner / evergreen)."""
    out_dir = settings.OUTPUT_DIR / item.date / item.slot
    paths, story_card = render_content(content_model(item), out_dir, item.date)
    gates.render_check(paths)
    item.media = [str(Path(p).as_posix()) for p in paths]
    item.story_media = str(Path(story_card).as_posix())
    return item


def words_used(content) -> list[str]:
    if isinstance(content, StoryPost):
        return [w.word for w in content.words]
    if isinstance(content, QuizPost):
        return [content.word.word]
    if isinstance(content, ConfusablesPost):
        return [w.word for w in content.pair]
    return []


def slot_when(plan: PlanItem) -> str:
    """'8 am' / '1 pm' / '8 pm' for the caption writer."""
    hhmm = plan.time_bst or settings.SLOT_TIMES.get(plan.slot, "08:00")
    h = int(hhmm.split(":")[0])
    return f"{(h % 12) or 12} {'am' if h < 12 else 'pm'}"


def quiz_answer_delay(plan: PlanItem) -> int:
    """Minutes until the quiz answer comment: 6 h, but never later than ~21:30 (before the last publish run)."""
    h, m = (int(x) for x in (plan.time_bst or settings.SLOT_TIMES.get(plan.slot, "08:00")).split(":"))
    return max(60, min(360, 21 * 60 + 30 - (h * 60 + m)))


def _mark_used(plan: PlanItem, content) -> None:
    W.mark_used(words_used(content), plan.date)
    if isinstance(content, GenericPost) and content.item_id:
        G.mark_item_used(G.spec_for(content.pillar) or {}, content.item_id)
    if isinstance(content, StoryPost) and content.source_title:
        from engine.news import mark_story_used
        mark_story_used(content.source_title, plan.date)


# ── one slot ───────────────────────────────────────────────────────────────
def build_item(plan: PlanItem, strategy: dict, dry_run: bool, use_critic: bool = True) -> QueueItem:
    item_id = f"{plan.date.replace('-', '')}-{plan.slot[:2]}-{uuid.uuid4().hex[:6]}"
    last_err = ""
    best: tuple[float, QueueItem, object] | None = None  # best near-miss: (score, item, content)
    for attempt in range(1, settings.MAX_GENERATION_ATTEMPTS + 1):
        log(f"  attempt {attempt}/{settings.MAX_GENERATION_ATTEMPTS} — {plan.pillar} ({plan.hook_style})")
        out_dir = settings.OUTPUT_DIR / plan.date / plan.slot / f"try{attempt}"  # a kept near-miss keeps its slides
        near_miss = False
        try:
            content = make_content(plan, strategy, attempt, previous_error=last_err)
            if isinstance(content, StoryPost):
                gates.story_words(content)
            summary = summarize(content)
            hook_instr = strategy["hook_styles"].get(plan.hook_style, {}).get("instruction", "")
            when = slot_when(plan)
            cap = write_caption(plan.pillar, summary, hook_instr, when,
                                layout=getattr(content, "layout", ""), hook_style=plan.hook_style,
                                previous_error=last_err)
            writer_model = llm.last_provider
            if isinstance(content, QuizPost) or (isinstance(content, GenericPost) and content.layout == "quiz"):
                # The body is fixed copy: the LLM may only write the hook, so the answer cannot leak.
                cap.body = "\n\n".join(settings.STRINGS.get("quiz_body") or [
                    "Four options on the image. One is right, three are close.",
                    "The answer and explanation come as a comment later today.",
                ])
                cap.comment_prompt = settings.STRINGS.get("quiz_comment_prompt") or "Your answer: A, B, C or D?"
            fb, ig, url = assemble(cap, plan.pillar, item_id, strategy, seed=attempt)
            gates.banned_claims(fb, ig, summary, allow_percent=(plan.pillar == "offer"))
            gates.caption_shape(fb, ig)
            gates.register(fb)
            if isinstance(content, ConfusablesPost):
                gates.headwords_in_english(fb, words_used(content))
            if isinstance(content, QuizPost):
                gates.quiz_caption_keeps_answer(fb, content.options[content.answer_index], content.word.gloss_bn)
            if isinstance(content, GenericPost) and content.quiz:
                gates.quiz_caption_keeps_answer(fb, content.quiz.options[content.quiz.answer_index], "")

            score, critic_model = 0.0, ""
            if use_critic:
                verdict = gates.critic(fb, summary, avoid=writer_model)
                critic_model = llm.last_provider
                score = verdict.score
                log(f"    critic: {verdict.score}/10 hook {verdict.hook_score} bangla_ok={verdict.bangla_ok} "
                    f"forced={verdict.forced_words} issues={verdict.issues[:2]}")
                if verdict.factual_error:
                    raise gates.GateError(f"critic found a factual error: {verdict.issues[:1]}")
                if verdict.forced_words and isinstance(content, StoryPost):
                    raise gates.GateError(f"critic flagged forced words {verdict.forced_words}")
                if not verdict.bangla_ok:
                    raise gates.GateError(f"critic: not spoken Banglish — {verdict.issues[:1]}")
                pass_mark = settings.OFFER_QUALITY_PASS if plan.pillar == "offer" else settings.QUALITY_PASS
                if verdict.score < pass_mark:
                    issues = f" — fix: {verdict.issues[:2]}" if verdict.issues else ""
                    if verdict.score < settings.NEAR_MISS_PASS:  # a weak post is never queued
                        raise gates.GateError(f"critic score {verdict.score} < {pass_mark}{issues}")
                    # Safe but not great: keep it as a fallback and try once more for a better one.
                    near_miss = True
                    last_err = f"GateError: critic score {verdict.score} < {pass_mark}{issues}"
                if verdict.hook_score < settings.HOOK_PASS and not verdict.improved_hook:
                    raise gates.GateError(f"critic hook score {verdict.hook_score} < {settings.HOOK_PASS}")
                if verdict.improved_hook and verdict.hook_score < settings.HOOK_PASS:
                    new_hook = verdict.improved_hook.strip()[:settings.HOOK_MAX_CHARS + 10]
                    fb = new_hook + fb[fb.index("\n"):]
                    ig = new_hook + ig[ig.index("\n"):]
                    gates.banned_claims(fb, ig, allow_percent=(plan.pillar == "offer"))
                    gates.caption_shape(fb, ig)
                    gates.register(fb)

            paths, story_card = render_content(content, out_dir, plan.date)
            gates.render_check(paths)
            gates.render_check([story_card], size=settings.STORY_CANVAS)

            first_comment, delay = "", 0
            if isinstance(content, GenericPost):
                first_comment, delay = G.first_comment(G.spec_for(content.pillar) or {}, content)
            elif isinstance(content, QuizPost):
                # Morning quiz: answer at ~14:00. Evening quiz: ~22:00, before the last publish heartbeat.
                first_comment, delay = P.quiz_answer_comment(content), quiz_answer_delay(plan)
            elif isinstance(content, StoryPost) and content.source_url and content.pillar == "news_word":
                first_comment = f"📰 Source: {content.source_title}\n{content.source_url}"

            item = QueueItem(
                id=item_id, date=plan.date, slot=plan.slot, pillar=plan.pillar, hook_style=plan.hook_style,
                content=content.model_dump(), caption_fb=fb, caption_ig=ig, first_comment=first_comment,
                comment_delay_minutes=delay, media=[str(Path(p).as_posix()) for p in paths],
                story_media=str(Path(story_card).as_posix()), quality_score=score, attempts=attempt, utm_url=url,
                writer_model=writer_model, critic_model=critic_model,
            )
            if near_miss:
                if best is None or score > best[0]:
                    best = (score, item, content)
                log(f"    ~ kept as fallback ({score}); trying for {pass_mark}")
                continue
            if not dry_run:
                _mark_used(plan, content)
            return item
        except (gates.GateError, ValueError, LLMError) as e:
            last_err = f"{type(e).__name__}: {e}"
            log(f"    ✗ {last_err}")
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            log(f"    ✗ unexpected: {last_err}")
            traceback.print_exc()
    if best is not None:
        score, item, content = best
        log(f"    using the best near-miss ({score})")
        if not dry_run:
            _mark_used(plan, content)
        return item
    return QueueItem(id=item_id, date=plan.date, slot=plan.slot, pillar=plan.pillar, hook_style=plan.hook_style,
                     status="failed", content={}, attempts=settings.MAX_GENERATION_ATTEMPTS, error=last_err)


def after_build(item: QueueItem, dry_run: bool, preview: bool = True) -> None:
    """Upload media + Telegram preview (skipped on dry-run or when not configured)."""
    if dry_run or item.status == "failed":
        return
    from engine.publishers import media_host, telegram
    if media_host.configured():
        try:
            item.media_urls = media_host.upload_many(item.media, f"{item.date}/{item.slot}/{item.id}")
            if item.story_media:
                item.story_media_url = media_host.upload_many([item.story_media], f"{item.date}/{item.slot}/{item.id}")[0]
            log(f"    uploaded {len(item.media_urls)} slides")
        except Exception as e:  # noqa: BLE001
            log(f"    ⚠ media upload failed: {e}")
    if preview and telegram.configured() and settings.REVIEW_MODE != "autopilot":
        try:
            item.telegram_message_id = telegram.send_preview(item)
            log("    telegram preview sent")
        except Exception as e:  # noqa: BLE001
            log(f"    ⚠ telegram failed: {e}")


# ── CLI ────────────────────────────────────────────────────────────────────
def run_dates(dates: list[str], pillar: str | None, dry_run: bool, force: bool, critic: bool,
              lineup: bool = False, not_before: datetime | None = None) -> int:
    """not_before: skip slots whose time is earlier than this (a morning slot is not made at night)."""
    strategy = load_strategy()
    failures = 0
    for date_str in dates:
        plans = plan_for_date(date_str, strategy)
        if pillar:
            plans = [PlanItem(date=date_str, slot=(plans[0].slot if plans else "morning"), pillar=pillar,
                              time_bst=(plans[0].time_bst if plans else "08:00"),
                              hook_style=(plans[0].hook_style if plans else "question"))]
        if not plans:
            log(f"{date_str}: no posts planned (holiday/skip)")
            continue
        for plan in plans:
            if not_before is not None and slot_datetime_bst(date_str, plan.time_bst) < not_before:
                continue
            path = queue_path(date_str, plan.slot)
            existing = load_item(path)
            if existing and existing.status not in ("failed",) and not force:
                log(f"{date_str} {plan.slot}: already queued ({existing.status}, {existing.pillar}) — skip")
                continue
            log(f"{date_str} {plan.slot}: generating {plan.pillar}")
            item = build_item(plan, strategy, dry_run, use_critic=critic)
            after_build(item, dry_run, preview=not lineup)
            save_item(item, path)
            if item.status == "failed":
                failures += 1
                log(f"  ✗ FAILED: {item.error}")
            else:
                log(f"  ✓ queued {item.id} score={item.quality_score} slides={len(item.media)} → {path}")
    return failures


def evergreen_left() -> int:
    """Backup posts still unused (used ones are renamed *.used / *.retired by publish)."""
    return sum(1 for f in settings.EVERGREEN_DIR.glob("*.json") if (it := load_item(f)) and it.status == "pending")


def run_evergreen(n: int, dry_run: bool, critic: bool) -> int:
    strategy = load_strategy()
    failures = 0
    base = datetime.now(settings.BST)
    pillars = [p for p in settings.EVERGREEN_PILLARS if p in CONTENT_TYPES or G.spec_for(p)] or ["quiz"]
    for i in range(n):
        pillar = pillars[i % len(pillars)]
        pseudo_date = (base + timedelta(days=1000 + i)).strftime("%Y-%m-%d")  # far future: no tracker collisions
        plan = PlanItem(date=pseudo_date, slot="morning", pillar=pillar, time_bst="08:00", hook_style="question")
        item = build_item(plan, strategy, dry_run=True, use_critic=critic)
        item.evergreen = True
        if item.status == "failed":
            failures += 1
            continue
        path = settings.EVERGREEN_DIR / f"{pillar}_{item.id}.json"
        save_item(item, path)
        log(f"  ✓ evergreen {path.name}")
    return failures


def review_date(now: datetime) -> str:
    """The posting day tonight's lineup is for. GitHub runs the 21:00 schedule late, sometimes after
    midnight: a run before 06:00 is still "tonight's" run and reviews today."""
    now = now.astimezone(settings.BST).replace(tzinfo=None)
    return (now if now.hour < 6 else now + timedelta(days=1)).strftime("%Y-%m-%d")


def fill_dates(now: datetime, days: int = 3) -> list[str]:
    """Today plus the following days: every run keeps a buffer, and a failed night is retried in time."""
    today = now.astimezone(settings.BST).replace(tzinfo=None)
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD (default: today BST)")
    ap.add_argument("--days", type=int, default=None, help="how many days from --date (default QUEUE_DAYS_AHEAD)")
    ap.add_argument("--pillar", help="built-in name or any project/pillars/<name>.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="regenerate even if a queue item exists")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--evergreen", type=int, default=0)
    ap.add_argument("--tomorrow", action="store_true", help="generate tomorrow (BST) only")
    ap.add_argument("--fill", action="store_true",
                    help="nightly: fill missing/failed slots from now through 2 days ahead, top up backups, "
                         "send the lineup for the next posting day")
    ap.add_argument("--repair", action="store_true", help="like --fill for today + tomorrow, no lineup, no backups")
    ap.add_argument("--lineup", action="store_true", help="send one numbered Telegram lineup per date instead of per-post cards")
    a = ap.parse_args(argv)
    dry = a.dry_run or settings.DRY_RUN

    if a.evergreen:
        return 1 if run_evergreen(a.evergreen, dry, not a.no_critic) else 0

    if a.fill or a.repair:
        now = datetime.now(settings.BST)
        dates = fill_dates(now, days=2 if a.repair else 3)
        # A slot up to 3 h past can still go out today (publish runs until 23:00); older ones are left alone.
        failures = run_dates(dates, None, dry, a.force, not a.no_critic, lineup=True,
                             not_before=now - timedelta(hours=3))
        if a.fill:
            short = settings.EVERGREEN_MIN - evergreen_left()
            if short > 0:
                log(f"backup pool: topping up {short}")
                run_evergreen(short, dry, not a.no_critic)
            if not dry:
                from engine.lineup import send_lineup
                send_lineup(review_date(now))
        return 1 if failures else 0

    start = datetime.strptime(a.date, "%Y-%m-%d") if a.date else datetime.now(settings.BST).replace(tzinfo=None)
    if a.tomorrow:
        now = datetime.now(settings.BST).replace(tzinfo=None)
        # GitHub runs the 21:00 schedule late, sometimes after midnight. A run before 06:00 BST is still
        # "tonight's" run: target today, or a whole day of posts would be skipped.
        start = now if now.hour < 6 else now + timedelta(days=1)
        a.days = 1
    days = a.days if a.days is not None else settings.QUEUE_DAYS_AHEAD
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(max(1, days))]
    failures = run_dates(dates, a.pillar, dry, a.force, not a.no_critic, lineup=a.lineup)
    if a.lineup and not dry:
        from engine.lineup import send_lineup
        for d in dates:
            send_lineup(d)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
