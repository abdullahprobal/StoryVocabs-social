"""Download the brand fonts once into render/assets/fonts/ (committed).

Google Fonts CSS API is queried with a modern-Chrome user agent so it returns
woff2 URLs; each face is saved as <family>-<weight><style>.woff2 and an index
fonts.json is written for the renderer (which inlines them as data URIs).
"""
import json
import re
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "render" / "assets" / "fonts"
OUT.mkdir(parents=True, exist_ok=True)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/128.0.0.0 Safari/537.36")

FAMILIES = {
    # family: [(weight, italic)]
    "Hind Siliguri": [(400, False), (500, False), (600, False), (700, False)],
    "Instrument Serif": [(400, False), (400, True)],
    "DM Sans": [(400, False), (500, False), (700, False)],
    "Tiro Bangla": [(400, False)],
}


def css_url(family: str, faces: list[tuple[int, bool]]) -> str:
    fam = family.replace(" ", "+")
    ital_w = sorted({(1 if i else 0, w) for w, i in faces})
    spec = ";".join(f"{i},{w}" for i, w in ital_w)
    return f"https://fonts.googleapis.com/css2?family={fam}:ital,wght@{spec}&display=swap"


def main():
    index = []
    for family, faces in FAMILIES.items():
        css = requests.get(css_url(family, faces), headers={"User-Agent": UA}, timeout=60).text
        blocks = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
        for b in blocks:
            style = re.search(r"font-style:\s*(\w+)", b).group(1)
            weight = int(re.search(r"font-weight:\s*(\d+)", b).group(1))
            url = re.search(r"url\((https://[^)]+\.woff2)\)", b).group(1)
            rng = re.search(r"unicode-range:\s*([^;]+);", b)
            subset = "bengali" if rng and "U+0980" in rng.group(1) else ("latin" if rng and "U+0000" in rng.group(1) else "other")
            if subset == "other":
                continue
            name = f"{family.replace(' ', '')}-{weight}{'i' if style == 'italic' else ''}-{subset}.woff2"
            path = OUT / name
            if not path.exists():
                path.write_bytes(requests.get(url, timeout=60).content)
            index.append({"family": family, "weight": weight, "style": style, "file": name,
                          "unicode_range": rng.group(1).strip() if rng else ""})
            print("ok", name, path.stat().st_size // 1024, "KB")
    (OUT / "fonts.json").write_text(json.dumps(index, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
