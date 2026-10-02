"""Renderer for project-defined pillars (GenericPost) — reuses the base templates.

carousel → cover.html + story.html per slide + recap.html (if items)
card     → offer.html
quiz     → quiz.html
"""
from __future__ import annotations

from pathlib import Path

from engine import settings
from render.image_renderer import S, _page, esc, fmt_date, footer_html, header_html, mark_hero, render_pages, ruby


def render_generic(post, out_dir: Path, date_str: str, label: str = "") -> list[str]:
    kicker = post.kicker or label
    if post.layout == "quiz" and post.quiz:
        letters = "ABCD"
        opts = "".join(f'<div class="opt"><span class="l">{letters[i]}</span><span>{esc(o)}</span></div>'
                       for i, o in enumerate(post.quiz.options))
        page = _page("quiz.html", {
            "HEADER": header_html(f'<span class="pill blue">{esc(label or "Quiz")}</span>'),
            "FOOTER": footer_html(S("quiz_footer", settings.STRINGS.get("footer_cta", ""))),
            "WORD": esc(post.headline), "PHONETIC": esc(post.subtitle), "POS": esc(post.kicker or ""),
            "PH_DISPLAY": "block" if (post.subtitle or post.kicker) else "none",
            "QUESTION": esc(post.quiz.question), "OPTIONS": opts, "EXAM": esc(S("quiz_tag", "")),
            "HINT": "", "HINT_DISPLAY": "none",
            "QUIZ_KICKER": S("quiz_kicker_line", "Do you know this one?"),
            "QUIZ_NOTE": S("quiz_note", "Answer in the comments — the correct one is posted later today"),
        })
        return render_pages([("slide_01_quiz.png", page, settings.CANVAS)], out_dir)

    if post.layout == "card":
        page = _page("offer.html", {
            "HEADER": header_html(""), "FOOTER": footer_html(),
            "KIND": esc(kicker), "HEADLINE_BN": esc(post.headline), "BODY_BN": esc(post.body),
            "DETAIL": esc(post.detail), "DETAIL_BLOCK": "flex" if post.detail else "none",
        })
        return render_pages([("slide_01_card.png", page, settings.CANVAS)], out_dir)

    n_story = len(post.slides)
    has_recap = bool(post.items)
    total = 1 + n_story + (1 if has_recap else 0)
    lead = post.items[0] if post.items else None
    pages = [("slide_01_cover.png", _page("cover.html", {
        "HEADER": header_html(f'<span class="pill">1 / {total}</span>'), "FOOTER": footer_html(),
        "CAT_CHIP": f'<span class="chip cat">{esc(label or post.pillar)}</span>', "DATE": fmt_date(date_str),
        "KICKER": esc(post.kicker or ""), "HEADLINE_HTML": mark_hero(post.headline), "HEADLINE_BN": esc(post.subtitle),
        "HERO_WORD": esc(lead.title if lead else ""), "HERO_GLOSS": esc(lead.sub if lead else ""),
        "HERO_POS": esc(lead.note if lead else ""),
        "SWIPE_N": str(n_story), "SWIPE_TEXT": S("swipe_generic", "Swipe"), "HERO_DISPLAY": "flex" if lead else "none",
    }), settings.CANVAS)]
    for i, s in enumerate(post.slides, 1):
        pages.append((f"slide_{1+i:02d}_story.png", _page("story.html", {
            "HEADER": header_html(f'<span class="pill">{1+i} / {total}</span>'), "FOOTER": footer_html(),
            "SECTION": esc(s.section_label.upper()), "PART": f"{i} / {n_story}" if n_story > 1 else "",
            "STORY_HTML": ruby(s.paragraph), "LEGEND": S("story_legend_generic", ""),
        }), settings.CANVAS))
    if has_recap:
        rows = "".join(f'<div class="row"><div class="num">{i}</div><div class="w">{esc(it.title)}'
                       f'<span class="pos">{esc(it.note)}</span></div><div class="g">{esc(it.sub)}</div></div>'
                       for i, it in enumerate(post.items, 1))
        pages.append((f"slide_{total:02d}_recap.png", _page("recap.html", {
            "HEADER": header_html(f'<span class="pill">{total} / {total}</span>'), "FOOTER": footer_html(),
            "N": str(len(post.items)), "ROWS": rows, "URL": esc(settings.SITE_DISPLAY),
            "RECAP_TITLE": S("recap_title_generic", "Recap"), "RECAP_SUB": S("recap_sub_generic", ""),
            "RECAP_CTA_HEAD": S("recap_cta_head", ""), "RECAP_CTA_SUB": S("recap_cta_sub", ""),
            "RECAP_CTA_BTN": S("recap_cta_button", "→"), "SOURCE": esc(post.source_title[:70]),
        }), settings.CANVAS))
    return render_pages(pages, out_dir)
