"""The 2026-09-19 'contrived' caption: every defect the owner felt must now be caught by code."""
import pytest

from engine import gates
from engine.publishers.telegram import parse_batch

TONIGHT = """২০২৬ এ জ্বালানি সংকট, কৃত্রিম সমাধান কি সত্যিই কাজ করবে?

শক্তি ঘাটতি শুধুই ফ্যাক্টরি নয়, ব্যাংক ও অফিসের ডেটা সেন্টারেও প্রভাব ফেলে।

Exam‑এ ‘Contrived’ শব্দের অর্থ কৃত্রিম, কিন্তু প্রশ্নে ‘natural’ বা ‘genuine’ বিকল্পের সঙ্গে গুলিয়ে না ফেলো।

মনে রাখার ট্রিক: ‘Contrived’ = ‘Created’ (কৃত্রিম) – যেন কোনো পরিকল্পনা কৃত্রিমভাবে তৈরি।

এই শব্দটা দিয়ে একটা বাক্য লিখে পাঠাও

৩টি প্যাক ফ্রি — লিংকে গিয়ে শুরু করো
storyvocabs.com/words/0919"""

GOOD = """গল্পের শেষটা বড্ড বানানো লাগল?

সেটাই contrived। যখন কোনো কিছু জোর করে মেলানো মনে হয় — natural না।

MCQ-তে 'artificial' আর 'contrived' দুটোই থাকলে, plot বা excuse-এর কথা হলে contrived-ই উত্তর।

কোন movie-র ending তোমার কাছে সবচেয়ে contrived লেগেছে?

৩টি প্যাক ফ্রি — লিংকে গিয়ে শুরু করো
storyvocabs.com/words/0920"""


def test_tonights_caption_is_rejected_by_register_gate():
    with pytest.raises(gates.GateError):
        gates.register(TONIGHT)


def test_equation_mnemonic_alone_is_rejected():
    with pytest.raises(gates.GateError, match="X = Y"):
        gates.register("Contrived = Created, মনে রাখো।\nstoryvocabs.com/words/0919")


def test_bookish_word_alone_is_rejected():
    with pytest.raises(gates.GateError, match="bookish"):
        gates.register("আজকের শক্তি ঘাটতি নিয়ে একটা শব্দ।\nstoryvocabs.com/words/0919")


def test_spoken_caption_passes():
    gates.register(GOOD)


def test_never_write_list_comes_from_voice_file():
    words = gates.bookish_words()
    assert "কৃত্রিম" in words and "শক্তি ঘাটতি" in words


def test_voice_command_parses():
    b = parse_batch("voice: never say কৃত্রিম, say বানানো")
    assert b == [{"kind": "voice", "numbers": None, "note": "never say কৃত্রিম, say বানানো"}]
    assert parse_batch("approve all")[0]["kind"] == "approve"


INCENSE = """ইনসেন্স নাকি ইনসেন্ট, কোনটা সঠিক?

মনে রাখো, ‘স’ = ধূপ, ‘ট’ = উদ্দীপনা।

৩টি প্যাক ফ্রি — লিংকে গিয়ে শুরু করো
storyvocabs.com/mixup/0620"""


def test_bangla_script_equation_is_rejected():
    with pytest.raises(gates.GateError, match="X = Y"):
        gates.register(INCENSE)


def test_confusables_caption_must_name_words_in_english():
    with pytest.raises(gates.GateError, match="English letters"):
        gates.headwords_in_english(INCENSE, ["Incense", "Intense"])
    gates.headwords_in_english("Stationary না stationery?\nstoryvocabs.com/mixup/1001", ["Stationary", "Stationery"])


def test_curated_pairs_are_distinct_and_picked_from_the_list():
    from engine.writers.pillars import confusable_pairs, pick_pair
    pairs = confusable_pairs()
    assert len(pairs) >= 50
    assert all(p["a"].lower() != p["b"].lower() for p in pairs)
    assert pick_pair("2026-09-27") in pairs


@pytest.mark.parametrize("text", ["do not post", "Don't approve", "dont post this", "stop", "পোস্ট করো না", "না", "বাদ দাও"])
def test_negative_replies_skip(text):
    from engine.publishers.telegram import classify
    assert classify(text)[0] == "skip"
    assert parse_batch(text)[0]["kind"] == "skip"


@pytest.mark.parametrize("text", ["post", "approve all", "ok", "বানানো দারুণ হয়েছে, post"])
def test_positive_replies_still_approve(text):
    assert parse_batch(text)[0]["kind"] == "approve"


def test_edit_note_with_bangla_na_is_not_a_skip():
    from engine.publishers.telegram import classify
    assert classify("edit: 'কৃত্রিম' লিখো না, 'বানানো' লিখো")[0] == "note"
