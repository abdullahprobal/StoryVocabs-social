"""One-time cleanup: recompute year usage counts from unique dates in the tracker."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

tracker_file = Path("word_usage_tracker.json")
tracker = json.loads(tracker_file.read_text(encoding="utf-8"))

fixed = 0
for word, entry in tracker.items():
    if "dates" in entry:
        for year in ["2026", "2025", "2024"]:
            unique_dates = set(d for d in entry["dates"] if d.startswith(year))
            if str(year) in entry:
                old_val = entry[str(year)]
                entry[str(year)] = len(unique_dates)
                if old_val != len(unique_dates):
                    fixed += 1

tracker_file.write_text(json.dumps(tracker, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Fixed {fixed} over-counted entries in tracker.")

overcount = {k: v for k, v in tracker.items() if isinstance(v.get("2026"), int) and v["2026"] > 3}
print(f"Words still over-limit: {len(overcount)}")
for w, v in list(overcount.items())[:5]:
    print(f"  {w}: {v['2026']} uses on dates {v.get('dates', [])}")
