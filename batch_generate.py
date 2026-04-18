"""
StoryVocabs Batch Generator — Pre-build up to 100+ posts in one run.

Usage:
    python batch_generate.py --days 25 --sessions-per-day 4
    python batch_generate.py --start-date 2026-04-17 --days 25 --sessions-per-day 4 --story-only
    python batch_generate.py --days 10 --sessions-per-day 2 --story-only

This produces days × sessions post batches, each containing 4 posts (slides carousel).
A batch_index.json manifest and BATCH_SCHEDULE.md are written to the output root.

Strategy:
  - Each (date, session) pair produces a unique batch:
      • Different word slice from the candidate pool
      • Different pair of news stories from the daily pool
      • Different story angle (data / human / historical / future)
  - news_pool.json is fetched once per date and cached (fast reruns)
  - time.sleep(DELAY_BETWEEN_SESSIONS) between sessions to respect API rate limits
  - --story-only skips image rendering (much faster); use rerender.py later
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Delay between sessions (seconds) — keeps API calls within rate limits
DELAY_BETWEEN_SESSIONS = 90
DELAY_BETWEEN_DATES = 30


def parse_args():
    args = {
        "start_date": None,
        "days": 25,
        "sessions_per_day": 4,
        "story_only": "--story-only" in sys.argv,
        "dry_run": "--dry-run" in sys.argv,
    }

    if "--start-date" in sys.argv:
        idx = sys.argv.index("--start-date")
        if idx + 1 < len(sys.argv):
            args["start_date"] = sys.argv[idx + 1]

    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            args["days"] = int(sys.argv[idx + 1])

    if "--sessions-per-day" in sys.argv:
        idx = sys.argv.index("--sessions-per-day")
        if idx + 1 < len(sys.argv):
            args["sessions_per_day"] = int(sys.argv[idx + 1])

    return args


def date_range(start_date_str, days):
    """Yield date strings from start_date for `days` days."""
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    for i in range(days):
        yield (start + timedelta(days=i)).strftime("%Y-%m-%d")


def is_session_complete(date_str, session):
    content_path = Path(__file__).parent / "output" / date_str / f"session_{session}" / "content.json"
    if not content_path.exists():
        return False
    try:
        data = json.loads(content_path.read_text(encoding="utf-8"))
        return len(data) == 4 and all(not v.get("needs_review", True) for v in data.values())
    except Exception:
        return False


def run_session(date_str, session, story_only, dry_run):
    """Run a single generate.py session. Returns True on success."""
    if is_session_complete(date_str, session):
        print(f"\n{'='*55}")
        print(f"  Date: {date_str} | Session: {session}")
        print(f"  ✓ Session already complete with all posts scored PASS. Skipping.")
        print(f"{'='*55}")
        return True

    cmd = [sys.executable, "generate.py", "--date", date_str, "--session", str(session)]
    if story_only:
        cmd.append("--story-only")

    print(f"\n{'='*55}")
    print(f"  Date: {date_str} | Session: {session}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"{'='*55}")

    if dry_run:
        print("  [DRY RUN] Skipping actual generation.")
        return True

    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(__file__).parent),
            capture_output=False,   # Show output in real time
            text=True,
            encoding="utf-8",
            timeout=600,            # 10 minutes max per session
        )
        if result.returncode != 0:
            print(f"  ⚠ Session returned exit code {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  ⚠ Session timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"  ⚠ Session error: {e}")
        return False


def collect_session_meta(date_str, session):
    """Read generated content.json and extract key metadata for the manifest."""
    output_dir = Path(__file__).parent / "output" / date_str / f"session_{session}"
    content_file = output_dir / "content.json"
    if not content_file.exists():
        return None

    try:
        data = json.loads(content_file.read_text(encoding="utf-8"))
        all_words = []
        scores = []
        needs_review_count = 0
        topic_titles = []
        for pk, pv in data.items():
            all_words.extend([w["word"] for w in pv.get("words", [])])
            scores.append(pv.get("quality_score", 0))
            if pv.get("needs_review"):
                needs_review_count += 1
            if pv.get("source_title") and pv["source_title"] not in topic_titles:
                topic_titles.append(pv["source_title"])

        unique_words = list(set(all_words))
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        return {
            "date": date_str,
            "session": session,
            "dir": str(output_dir),
            "words": unique_words,
            "word_count": len(unique_words),
            "avg_quality_score": avg_score,
            "needs_review_posts": needs_review_count,
            "topics": topic_titles[:2],
        }
    except Exception as e:
        print(f"  Meta read error: {e}")
        return None


def write_batch_index(manifest, output_root):
    """Write batch_index.json manifest."""
    index_path = output_root / "batch_index.json"
    index_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n✓ batch_index.json → {index_path}")


def write_batch_schedule(manifest, output_root):
    """Write human-readable BATCH_SCHEDULE.md."""
    lines = [
        "# StoryVocabs Batch Schedule",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total batches: {manifest['generated']} | Total posts: {manifest['generated'] * 4}",
        "",
        "---",
        "",
        "| # | Date | Session | Angle | Words | Avg Score | Topics | Status |",
        "|---|------|---------|-------|-------|-----------|--------|--------|",
    ]

    angles = {1: "📊 Data", 2: "🧑 Human", 3: "🏛 History", 4: "🔭 Future"}
    failed_entries = []

    for i, post in enumerate(manifest["posts"], 1):
        angle = angles.get(post.get("session", 1), "—")
        words_str = ", ".join(post.get("words", [])[:5])
        if len(post.get("words", [])) > 5:
            words_str += "..."
        score = post.get("avg_quality_score", "—")
        topics = " / ".join(t[:40] for t in post.get("topics", [])[:2])
        nr = post.get("needs_review_posts", 0)
        status = f"⚠ {nr} review" if nr else "✓"

        lines.append(
            f"| {i} | {post['date']} | S{post['session']} | {angle} | {words_str} "
            f"| {score} | {topics} | {status} |"
        )

        if nr:
            failed_entries.append(f"- Batch {i} ({post['date']} S{post['session']}): {nr} posts need review")

    if failed_entries:
        lines += ["", "## Posts Needing Review", ""]
        lines.extend(failed_entries)

    # Summary stats
    valid_scores = [p["avg_quality_score"] for p in manifest["posts"] if isinstance(p.get("avg_quality_score"), (int, float))]
    if valid_scores:
        overall_avg = round(sum(valid_scores) / len(valid_scores), 1)
        lines += [
            "",
            "## Summary",
            "",
            f"- **Average quality score:** {overall_avg}/10",
            f"- **Batches generated:** {manifest['generated']}",
            f"- **Total 4-post carousels:** {manifest['generated']}",
            f"- **Total slides:** {manifest['generated'] * 4 * 3} (est.)",
            f"- **Failed sessions:** {manifest['failed']}",
        ]

    schedule_path = output_root / "BATCH_SCHEDULE.md"
    schedule_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ BATCH_SCHEDULE.md → {schedule_path}")


def main():
    args = parse_args()

    start_date_str = args["start_date"] or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    days = args["days"]
    sessions_per_day = args["sessions_per_day"]
    story_only = args["story_only"]
    dry_run = args["dry_run"]

    total_sessions = days * sessions_per_day

    print("=" * 60)
    print("  StoryVocabs Batch Generator")
    print(f"  Start date:  {start_date_str}")
    print(f"  Days:        {days}")
    print(f"  Sessions/day:{sessions_per_day}")
    print(f"  Total:       {total_sessions} post batches ({total_sessions * 4} posts)")
    print(f"  Story only:  {story_only}")
    print(f"  Dry run:     {dry_run}")
    print("=" * 60)
    print()

    if not dry_run:
        confirm = input(f"Generate {total_sessions} batches? This will use API credits. [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    output_root = Path(__file__).parent / "output"
    output_root.mkdir(exist_ok=True)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "start_date": start_date_str,
        "days": days,
        "sessions_per_day": sessions_per_day,
        "generated": 0,
        "failed": 0,
        "posts": [],
    }

    post_id = 1
    for date_str in date_range(start_date_str, days):
        print(f"\n{'#'*60}")
        print(f"# Date: {date_str}  ({days - list(date_range(start_date_str, days)).index(date_str)} days remaining)")
        print(f"{'#'*60}")

        for session in range(1, sessions_per_day + 1):
            success = run_session(date_str, session, story_only, dry_run)

            meta = collect_session_meta(date_str, session)
            if meta:
                meta["post_id"] = post_id
                manifest["posts"].append(meta)
                manifest["generated"] += 1
                print(f"  ✓ Batch {post_id}: score={meta['avg_quality_score']}, words={meta['word_count']}")
            else:
                manifest["failed"] += 1
                manifest["posts"].append({
                    "post_id": post_id,
                    "date": date_str,
                    "session": session,
                    "status": "failed",
                })
                print(f"  ✗ Batch {post_id}: FAILED")

            post_id += 1

            # Save manifest incrementally (resume safety)
            write_batch_index(manifest, output_root)

            # Delay between sessions to respect API rate limits
            if session < sessions_per_day:
                print(f"  Waiting {DELAY_BETWEEN_SESSIONS}s before next session...")
                if not dry_run:
                    time.sleep(DELAY_BETWEEN_SESSIONS)

        # Delay between dates
        if date_str != list(date_range(start_date_str, days))[-1]:
            print(f"\n  Waiting {DELAY_BETWEEN_DATES}s before next date...")
            if not dry_run:
                time.sleep(DELAY_BETWEEN_DATES)

    # Final manifest and schedule
    write_batch_index(manifest, output_root)
    write_batch_schedule(manifest, output_root)

    print()
    print("=" * 60)
    print(f"  BATCH COMPLETE")
    print(f"  Generated: {manifest['generated']} / {total_sessions}")
    print(f"  Failed:    {manifest['failed']}")
    print("=" * 60)
    print()
    print(f"Next steps:")
    print(f"  1. Review BATCH_SCHEDULE.md for quality scores and flagged posts")
    print(f"  2. Regenerate any 'needs_review' batches manually:")
    print(f"       python generate.py --date YYYY-MM-DD --session N")

    if story_only:
        print(f"  3. Render images for all batches:")
        print(f"       for each output/DATE/session_N/content.json: python rerender.py")

    print()


if __name__ == "__main__":
    main()
