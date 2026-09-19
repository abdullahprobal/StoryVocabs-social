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
