"""Vendor the app's word packs into data/word_packs.json.

The social engine must not depend on the app repo being checked out (CI has
only this repo). Run this whenever the app's packs change:

    python scripts/sync_word_packs.py [path/to/frontend/src/data]

Default source: the launch working copy of the app.
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_SRC = Path(r"C:\Users\DELL\.antigravity\Story-Vocabulary app\source\frontend\src\data")
OUT = Path(__file__).resolve().parent.parent / "data" / "word_packs.json"


def extract_array(js_text: str) -> list:
    """Return the first top-level array literal (`export const x = [ ... ];`)."""
    start = js_text.find("[")
    end = js_text.find("\n];", start)
    end = js_text.rfind("]") if end == -1 else end + 1
    if start == -1 or end == -1:
        raise ValueError("no JSON array found")
    body = js_text[start : end + 1]
    # strip trailing commas that JS tolerates but JSON does not
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    packs = []
    for name in ("wordPacks.js", "wordPacksGenerated.js"):
        p = src / name
        if not p.exists():
            print(f"skip {name} (missing)")
            continue
        try:
            arr = extract_array(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"skip {name}: {e}")
            continue
        packs.extend(arr)
        print(f"{name}: {len(arr)} packs")
    # Enrich with the app's example sentences and synonym data (same merge the app does)
    sentences = json.loads((src / "sentences_cache.json").read_text(encoding="utf-8")) if (src / "sentences_cache.json").exists() else {}
    synonyms = json.loads((src / "synonyms.json").read_text(encoding="utf-8")) if (src / "synonyms.json").exists() else {}
    seen = set()
    for pack in packs:
        for w in pack.get("words", []):
            key = w.get("word", "").strip().upper()
            if not w.get("sentence") and key in sentences:
                w["sentence"] = sentences[key]
            syn = synonyms.get(key) if isinstance(synonyms, dict) else None
            if isinstance(syn, dict):
                w.setdefault("synonym", syn.get("synonym") or syn.get("synonyms"))
                w.setdefault("antonym", syn.get("antonym") or syn.get("antonyms"))
            w["pos"] = w.get("pos") or w.get("partOfSpeech") or ""
            w["difficulty"] = pack.get("difficulty", "Intermediate")
            w["pack_id"] = pack.get("id")
            w["pack_title"] = pack.get("title")
            seen.add(key)
    words = len(seen)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"packs": packs, "pack_count": len(packs), "word_count": words},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(packs)} packs, {words} words)")


if __name__ == "__main__":
    main()
