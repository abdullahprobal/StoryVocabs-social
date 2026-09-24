"""Weekly feedback loop.

    python -m engine.insights            # collect metrics for posts published in the last 14 days,
                                         # re-weight pillars/hook styles, write analytics/, notify Telegram

Metrics per post (Meta Insights):
  FB : reach (post_total_media_view_unique, falling back to post_impressions_unique), clicks, reactions, shares, comments
  IG : reach, saved, shares, likes, comments

Engagement score per post = (saves*3 + shares*3 + comments*2 + clicks*2 + reactions) / max(reach, 50)
Weights: new_weight = 0.7*old + 0.3*(score / mean_score), clamped to [0.4, 2.0]. Pillars with no
data keep their weight. Also checks the Page token expiry and warns 14 days ahead.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timedelta, timezone

from engine import settings
from engine.contracts import QueueItem
from engine.generate import load_item, save_item
from engine.planner import load_strategy, save_strategy
from engine.publishers import meta, telegram

POSTS_LOG = settings.ANALYTICS_DIR / "posts.jsonl"


def log(msg: str) -> None:
    print(msg, flush=True)


def score(m: dict) -> float:
    reach = max(m.get("reach") or 0, 50)
    return ((m.get("saves") or 0) * 3 + (m.get("shares") or 0) * 3 + (m.get("comments") or 0) * 2
            + (m.get("clicks") or 0) * 2 + (m.get("reactions") or 0)) / reach * 100


def collect(item: QueueItem) -> dict:
    m = {"id": item.id, "date": item.date, "pillar": item.pillar, "hook_style": item.hook_style,
         "fb_post_id": item.fb_post_id, "ig_media_id": item.ig_media_id}
    if item.fb_post_id:
        try:
            fb = meta.fb_post_insights(item.fb_post_id)
            m.update({k: fb.get(k) or 0 for k in ("reach", "clicks", "reactions", "shares", "comments")})
        except meta.MetaError as e:
            m["fb_error"] = str(e)
    if item.ig_media_id:
        try:
            ig = meta.ig_media_insights(item.ig_media_id)
            m.update({"ig_reach": ig.get("reach") or 0, "saves": ig.get("saved") or 0,
                      "ig_shares": ig.get("shares") or 0, "ig_likes": ig.get("likes") or 0,
                      "ig_comments": ig.get("comments") or 0})
            m["reach"] = (m.get("reach") or 0) + (ig.get("reach") or 0)
            m["shares"] = (m.get("shares") or 0) + (ig.get("shares") or 0)
            m["comments"] = (m.get("comments") or 0) + (ig.get("comments") or 0)
        except meta.MetaError as e:
            m["ig_error"] = str(e)
    m["score"] = round(score(m), 2)
    m["collected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return m


def reweight(strategy: dict, rows: list[dict]) -> dict:
    by_pillar: dict[str, list[float]] = {}
    by_hook: dict[str, list[float]] = {}
    for r in rows:
        if r.get("reach", 0) < 20:
            continue
        by_pillar.setdefault(r["pillar"], []).append(r["score"])
        by_hook.setdefault(r.get("hook_style", ""), []).append(r["score"])
    all_scores = [s for v in by_pillar.values() for s in v]
    if len(all_scores) < 3:
        return strategy
    mean = statistics.mean(all_scores) or 1.0

    def upd(old: float, scores: list[float]) -> float:
        rel = statistics.mean(scores) / mean if scores else 1.0
        return round(max(0.4, min(2.0, 0.7 * old + 0.3 * rel)), 3)

    for p, w in strategy.get("pillar_weights", {}).items():
        if p in by_pillar:
            strategy["pillar_weights"][p] = upd(float(w), by_pillar[p])
    for h, cfg in strategy.get("hook_styles", {}).items():
        if h in by_hook:
            cfg["weight"] = upd(float(cfg.get("weight", 1.0)), by_hook[h])
    return strategy


def main() -> int:
    if not meta.configured():
        log("META credentials not set; nothing to collect")
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    rows = []
    for f in sorted(settings.QUEUE_DIR.glob("*/*.json")):
        item = load_item(f)
        if not item or item.status != "published" or item.date < since:
            continue
        rows.append(collect(item))
    settings.ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    with POSTS_LOG.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    week = datetime.now(timezone.utc).strftime("%G-W%V")
    (settings.ANALYTICS_DIR / f"{week}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    strategy = load_strategy()
    strategy = reweight(strategy, rows)
    save_strategy(strategy)

    # report
    lines = [f"📊 Weekly report {week} — {len(rows)} posts"]
    for r in sorted(rows, key=lambda x: -x["score"])[:7]:
        lines.append(f"• {r['date']} {r['pillar']}/{r.get('hook_style','')}: reach {r.get('reach',0)} · "
                     f"saves {r.get('saves',0)} · shares {r.get('shares',0)} · comments {r.get('comments',0)} · "
                     f"clicks {r.get('clicks',0)} → {r['score']}")
    lines.append("Weights: " + ", ".join(f"{k} {v}" for k, v in strategy["pillar_weights"].items()))
    try:
        info = meta.token_info()
        exp = info.get("expires_at") or 0
        if exp:
            days = (datetime.fromtimestamp(exp, tz=timezone.utc) - datetime.now(timezone.utc)).days
            lines.append(f"Page token: {days} days left" + (" ⚠ RENEW SOON" if days < 14 else ""))
        else:
            lines.append("Page token: never expires ✅")
    except meta.MetaError as e:
        lines.append(f"Page token check failed: {e}")
    report = "\n".join(lines)
    log(report)
    telegram.notify(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
