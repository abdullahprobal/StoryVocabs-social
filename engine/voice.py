"""Brand voice: the system prompt shared by every writer and the caption engine.

Everything here comes from project/: voice.md (how to write) and facts.json (what may be
claimed). The engine never hard-codes a brand, so the same code serves any project.
"""
from __future__ import annotations

import json

from engine import settings


def product_facts() -> dict:
    return json.loads(settings.FACTS_FILE.read_text(encoding="utf-8"))


def _fmt(value) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_fmt(v)}" for k, v in value.items() if not str(k).startswith("_"))
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value)
    return str(value)


def facts_block() -> str:
    """Render facts.json into the 'only claims allowed' block.

    Two shapes are accepted:
      * generic  — {"claims": ["81 word packs", ...], "never_say": [...]}
      * free-form — any other keys are rendered as `key: value` lines (numbers, plans, features...)
    """
    f = product_facts()
    lines = []
    if f.get("claims"):
        lines += [f"- {c}" for c in f["claims"]]
    for k, v in f.items():
        if k in ("claims", "never_say") or str(k).startswith("_"):
            continue
        lines.append(f"- {k}: {_fmt(v)}")
    never = ", ".join(f.get("never_say", []))
    return ("PRODUCT FACTS (the only claims allowed):\n" + "\n".join(lines) +
            f"\n- Website: {settings.PUBLIC_SITE_URL}\n"
            + (f"NEVER say any of: {never}. " if never else "")
            + "Never invent statistics, research, competitor prices or testimonials.")


def _voice_text() -> str:
    p = settings.VOICE_FILE
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    b = settings.PROJECT.get("brand", {})
    return (f"You write social media content for {b.get('name', 'the brand')}. "
            f"Audience: {settings.PROJECT.get('audience', '')}. Be specific, honest, warm; no hype.")


SYSTEM = f"""{_voice_text()}

{facts_block()}
"""
