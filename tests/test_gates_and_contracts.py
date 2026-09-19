import pytest

from engine import gates, settings
from engine.caption import assemble
from engine.contracts import Caption, QuizPost, StoryPost, Word
from engine.planner import load_strategy, plan_for_date
from tests.fixtures_story import NEWS_POST


def _caption():
    return Caption(hook_line="BCS-তে Candor এলে কী লিখবে?", body="Candor মানে অকপটতা।\n\nExam-এ noun হিসেবে আসে।",
                   comment_prompt="একটা বাক্য লিখো তো", cta_line="৩টি প্যাক ফ্রি — লিংকে গিয়ে শুরু করো",
                   hashtags=["Candor", "বিসিএস", "IELTS", "Vocabulary", "Dhaka"])


def test_assemble_has_one_fb_url_and_no_ig_url():
    fb, ig, url = assemble(_caption(), "news_word", "abc", load_strategy())
    gates.caption_shape(fb, ig)
    assert url.startswith(settings.PUBLIC_SITE_URL)
    assert "utm_campaign=news_word" in url
    assert f"{settings.SITE_DISPLAY}/words" in fb and "http" not in fb and settings.SITE_DISPLAY not in ig


def test_display_link_is_vanity_with_day_tag():
    from engine.caption import build_display_url, build_utm
    assert build_display_url("quiz", "20260920-mo-6ed355") == f"{settings.SITE_DISPLAY}/quiz/0920"
    assert build_display_url("offer", "x") == f"{settings.SITE_DISPLAY}/free"
    assert "utm_content=0920" in build_utm("quiz", "20260920-mo-6ed355")
    fb, ig, _ = assemble(_caption(), "quiz", "20260920-mo-6ed355", load_strategy())
    assert "/go/" not in fb and "6ed355" not in fb


def test_banned_claims_blocks_harvard_and_stats():
    with pytest.raises(gates.GateError):
        gates.banned_claims("হার্ভার্ড ইউনিভার্সিটির গবেষণায় প্রমাণিত")
    with pytest.raises(gates.GateError):
        gates.banned_claims("গবেষণায় দেখা গেছে ৫ গুণ বেশি মনে থাকে")
    with pytest.raises(gates.GateError):
        gates.banned_claims("90% students fail this")
    with pytest.raises(gates.GateError):
        gates.banned_claims("visit storyvocabs.vercel.app")
    gates.banned_claims("81 word packs, 1,608 words, 3 packs free")


def test_caption_shape_rejects_second_link_and_long_hook():
    fb, ig, _ = assemble(_caption(), "quiz", "x", load_strategy())
    with pytest.raises(gates.GateError):
        gates.caption_shape(fb + "\nhttps://example.com", ig)
    with pytest.raises(gates.GateError):
        gates.caption_shape("x" * 200 + fb, ig)


def test_story_words_gate_passes_fixture_and_fails_when_unmarked():
    gates.story_words(NEWS_POST)
    broken = NEWS_POST.model_copy(deep=True)
    broken.story_slides[0].paragraph = broken.story_slides[0].paragraph.replace("[[compile|একত্রিত করা]]", "compile")
    with pytest.raises(gates.GateError):
        gates.story_words(broken)


def test_headline_bn_strips_markup_and_example_must_be_english():
    p = StoryPost(**{**NEWS_POST.model_dump(), "headline_bn": "জয়ের পর [[candor|অকপটতা]] দেখাল বোর্ড"})
    assert "[[" not in p.headline_bn and "candor" in p.headline_bn
    w = Word(word="test", gloss_bn="পরীক্ষা", meaning_bn="x", meaning_en="y", example="এটা বাংলা বাক্য test")
    assert w.example == ""


def test_hero_must_be_in_words():
    with pytest.raises(ValueError):
        StoryPost(**{**NEWS_POST.model_dump(), "hero_word": "zebra"})


def test_quiz_options_distinct():
    w = Word(word="revere", gloss_bn="শ্রদ্ধা করা", meaning_bn="x", meaning_en="y")
    with pytest.raises(ValueError):
        QuizPost(word=w, question_bn="?", options=["a", "a", "b", "c"], answer_index=0, explanation_bn="e")


def test_planner_calendar_and_holidays():
    strat = load_strategy()
    hol = {"skip_dates": {"2026-09-26": "test"}, "single_evening_post_dates": {"2026-09-27": "eid2"}, "ramadan_windows": []}
    assert plan_for_date("2026-09-26", strat, hol) == []
    eid2 = plan_for_date("2026-09-27", strat, hol)
    assert len(eid2) == 1 and eid2[0].slot == "evening"
    fri = plan_for_date("2026-09-25", strat, hol)  # Friday
    assert fri and fri[0].pillar == "offer" and fri[0].slot == "evening"
    sat = plan_for_date("2026-09-19", strat, hol)
    assert sat[0].pillar == "news_word" and sat[0].topic_group == "politics"
    quiz = plan_for_date("2026-09-20", strat, hol)
    assert quiz[0].pillar == "quiz" and quiz[0].hook_style in ("question", "mistake", "exam_angle")


def test_llm_extract_json_handles_fences():
    from engine.llm import extract_json
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json('text before {"a": {"b": 2}} after') == '{"a": {"b": 2}}'
