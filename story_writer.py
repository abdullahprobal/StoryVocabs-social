"""Generates human-quality stories for 4 posts/day: short bites and deep dives.

API Strategy:
  Primary: OpenRouter (Qwen 3 Next 80B A3B — best Bangla support)
  Fallback: Groq (Llama 3.3 70B)

Key improvements over v1:
  - Topic-first word alignment: words are selected AFTER news topic is known,
    ensuring every vocabulary word fits naturally in the story context.
  - Batched alignment: 1 LLM call selects all 10 words for both topics at once.
  - Story angle injection: cycles across sessions for variety (data / human / history / future).
  - Quality threshold raised from 5.5 → 7.0; failed stories flagged not discarded.
"""

import re
import json
import time
import requests
from groq import Groq
from config import (
    GROQ_API_KEYS, GROQ_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL,
    USE_OPENROUTER_AS_PRIMARY,
)
from word_pack_manager import load_tracker, save_tracker, mark_used, build_word_sets_from_alignment

QUALITY_PASS_THRESHOLD = 7.0

# Story angles cycle across sessions to guarantee variety on your feed
STORY_ANGLES = {
    1: "Focus on data, statistics, and factual insights. Use concrete numbers where possible.",
    2: "Focus on human impact — what this news means for ordinary Bangladeshi people in their daily lives.",
    3: "Focus on historical context — how Bangladesh arrived at this moment and what the past tells us.",
    4: "Focus on future outlook — what comes next, possible solutions, and what to watch for.",
}


def clean_json_response(raw):
    """Extract JSON from any LLM response."""
    if not raw:
        return None
    raw = raw.strip()
    while "```" in raw:
        first = raw.find("```")
        last = raw.find("```", first + 3)
        if last == -1:
            raw = raw[first + 3:]
            break
        raw = raw[first + 3:last]
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].lstrip("\n").lstrip()
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"      JSON error: {e}")
        return None


def call_openrouter(messages, temperature=0.7, max_tokens=3000, retries=3, model=OPENROUTER_MODEL):
    """Call OpenRouter API (Qwen/Gemma), return parsed JSON."""
    if not OPENROUTER_API_KEY:
        print("      OpenRouter key not set, skipping")
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://storyvocabs.vercel.app",
                    "X-Title": "StoryVocabs Social",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"      Rate limited, waiting {wait}s (attempt {attempt+1}/{retries})...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            if not raw:
                return None
            return clean_json_response(raw)
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait = 3 * (attempt + 1)
                print(f"      Request error, retry in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"      OpenRouter error: {e}")
                return None
        except Exception as e:
            print(f"      OpenRouter error: {e}")
            return None
    return None


def call_groq(messages, temperature=0.7, max_tokens=3000, model=GROQ_MODEL):
    """Call Groq API, return parsed JSON. Automatically rotates keys on rate limit."""
    from config import GROQ_API_KEYS
    import json

    if not GROQ_API_KEYS:
        print("      Groq keys not set, skipping")
        return None

    # Track how many keys we've tried to avoid infinite loops
    attempts = 0
    max_attempts = len(GROQ_API_KEYS)
    
    while attempts < max_attempts:
        # Get the first key in the current rotation state
        current_key = GROQ_API_KEYS[0]
        
        try:
            client = Groq(api_key=current_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content
            if not raw:
                return None
            return clean_json_response(raw)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate limit" in error_str.lower():
                # On rate limit, rotate this key to the back of the list and try the next one
                print(f"      [Key {str(current_key)[-4:]}] Rate limited. Rotating to next key...")
                GROQ_API_KEYS.append(GROQ_API_KEYS.pop(0))
                attempts += 1
            else:
                print(f"      Groq error: {e}")
                return None
                
    print(f"      All {max_attempts} Groq keys are currently rate-limited.")
    return None


def call_llm(messages, temperature=0.7, max_tokens=3000):
    """Call primary LLM with automatic fallback to secondary models."""
    from config import OPENROUTER_FALLBACK_MODEL

    if USE_OPENROUTER_AS_PRIMARY:
        print("      → OpenRouter Primary (Qwen 3 Next 80B)...")
        result = call_openrouter(messages, temperature, max_tokens)
        if result: return result

        print("      → OpenRouter Secondary (Gemma 4 31B)...")
        result = call_openrouter(messages, temperature, max_tokens, model=OPENROUTER_FALLBACK_MODEL)
        if result: return result

        print("      → Fallback to Groq Primary (Llama 3.3 70B)...")
        result = call_groq(messages, temperature, max_tokens)
        if result: return result

        print("      → APIs exhausted. Waiting 30s then trying Groq Secondary (Llama 3.1 8B)...")
        time.sleep(30)
        return call_groq(messages, temperature, max_tokens, model="llama-3.1-8b-instant")
    else:
        print("      → Groq Primary (Llama 3.3 70B)...")
        result = call_groq(messages, temperature, max_tokens)
        if result: return result

        print("      → Fallback to OpenRouter Primary (Qwen)...")
        result = call_openrouter(messages, temperature, max_tokens)
        if result: return result

        print("      → APIs exhausted. Waiting 30s then trying Groq Secondary (Llama 3.1 8B)...")
        time.sleep(30)
        return call_groq(messages, temperature, max_tokens, model="llama-3.1-8b-instant")


# ─── WORD-TOPIC ALIGNMENT ──────────────────────────────────────────────────────

WORD_ALIGNMENT_PROMPT = """You are a vocabulary curriculum designer for a Bangladeshi social media learning app.

Your job is to select vocabulary words that fit NATURALLY into stories about specific news topics.
A word fits naturally only if it could realistically appear in a fluent, authentic news story about that topic.

TOPIC A (need 3 words for short post + 2 additional new words for expanded post):
Title: {topic_a_title}
Summary: {topic_a_summary}

TOPIC B (need 3 words for short post + 2 additional new words for expanded post):
Title: {topic_b_title}
Summary: {topic_b_summary}

CANDIDATE WORD POOL ({count} words):
{word_list}

SELECTION RULES:
- Select words where a FLUENT writer would NATURALLY choose that word in a story about that topic
- Avoid words that feel forced or require the story to awkwardly pivot around them
- Topic A and Topic B should use DIFFERENT words (no overlap)
- Each topic needs exactly 3 (short) + 2 (new_for_long) = 5 total unique words
- If a word genuinely fits both topics, always assign it to Topic A

Return ONLY valid JSON:
{{
  "topic_a": {{
    "short": ["word1", "word2", "word3"],
    "new_for_long": ["word4", "word5"]
  }},
  "topic_b": {{
    "short": ["word6", "word7", "word8"],
    "new_for_long": ["word9", "word10"]
  }},
  "reasoning": "Brief note on why these words fit"
}}"""


def build_candidate_list(candidates):
    """Format candidate words for the alignment prompt."""
    lines = []
    for i, w in enumerate(candidates, 1):
        lines.append(
            f"{i}. {w['word']} ({w.get('partOfSpeech', '')}) "
            f"— {w.get('meaning', w.get('bangla', ''))}"
        )
    return "\n".join(lines)


def resolve_words_by_name(names, candidates):
    """Look up full word dicts from candidate list by word name."""
    name_map = {w["word"].lower(): w for w in candidates}
    resolved = []
    for name in names:
        w = name_map.get(name.lower())
        if w:
            resolved.append(dict(w))
    return resolved


def select_words_for_session(candidates, topic_a, topic_b, session=1):
    """One batched LLM call to select words for BOTH topics simultaneously.

    This is the core quality fix: words are chosen AFTER topics are known,
    so only semantically compatible words are assigned to each story.

    Args:
        candidates: List of 30 candidate word dicts from get_candidate_words().
        topic_a: News dict with 'title' and 'summary' for Topic A.
        topic_b: News dict with 'title' and 'summary' for Topic B.
        session: Session number (1-4), used for angle logging.

    Returns:
        word_sets dict compatible with build_word_sets_from_alignment(), or None on failure.
    """
    word_list = build_candidate_list(candidates)
    prompt = WORD_ALIGNMENT_PROMPT.format(
        topic_a_title=topic_a.get("title", ""),
        topic_a_summary=topic_a.get("summary", "")[:300],
        topic_b_title=topic_b.get("title", ""),
        topic_b_summary=topic_b.get("summary", "")[:300],
        word_list=word_list,
        count=len(candidates),
    )

    print(f"\n  ┌─ Word-Topic Alignment (Session {session}, 1 LLM call for both topics)...")
    result = call_llm(
        [
            {"role": "system", "content": "You select vocabulary words for news stories. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=400,
    )

    if not result:
        print("  │  Alignment failed, will use positional fallback")
        return None

    print(f"  │  Reasoning: {result.get('reasoning', 'N/A')[:100]}")

    # Resolve word names to full dicts
    try:
        ta = result.get("topic_a", {})
        tb = result.get("topic_b", {})

        a_short = resolve_words_by_name(ta.get("short", []), candidates)
        a_long  = resolve_words_by_name(ta.get("new_for_long", []), candidates)
        b_short = resolve_words_by_name(tb.get("short", []), candidates)
        b_long  = resolve_words_by_name(tb.get("new_for_long", []), candidates)

        # Validate — need at least 3 for short, 2 for long
        if len(a_short) < 3 or len(a_long) < 2 or len(b_short) < 3 or len(b_long) < 2:
            print(f"  │  Insufficient words returned: A_short={len(a_short)}, A_long={len(a_long)}, "
                  f"B_short={len(b_short)}, B_long={len(b_long)}")
            # Retry with a larger pool fallback — handled by caller
            return None

        # Ensure 3 / 2 exactly
        a_short = a_short[:3]
        a_long  = a_long[:2]
        b_short = b_short[:3]
        b_long  = b_long[:2]

        print(f"  │  Topic A: {', '.join(w['word'] for w in a_short + a_long)}")
        print(f"  └─ Topic B: {', '.join(w['word'] for w in b_short + b_long)}")

        return build_word_sets_from_alignment(
            {"short": a_short, "new_for_long": a_long},
            {"short": b_short, "new_for_long": b_long},
        )

    except Exception as e:
        print(f"  │  Alignment parse error: {e}")
        return None


def positional_word_sets_fallback(candidates):
    """Fallback: assign words positionally if alignment fails."""
    pool = candidates[:10] if len(candidates) >= 10 else candidates
    while len(pool) < 10:
        pool = pool + candidates[:10 - len(pool)]

    post_1_words = pool[:3]
    post_2_new   = pool[3:5]
    post_3_words = pool[5:8]
    post_4_new   = pool[8:10]

    print("  └─ Using positional fallback for word sets")
    return build_word_sets_from_alignment(
        {"short": post_1_words, "new_for_long": post_2_new},
        {"short": post_3_words, "new_for_long": post_4_new},
    )


# ─── STORY PROMPTS ────────────────────────────────────────────────────────────

SHORT_PROMPT = """You are a Bangladeshi content creator for StoryVocabs — a vocabulary learning app. Write a SHORT, engaging social media post about a news topic.

NEWS TOPIC:
Headline: {news_title}
Details: {news_summary}

TARGET WORDS (you MUST use ALL of them naturally in the story):
{word_list}

STORY ANGLE: {story_angle}

RULES:
- Write about {word_count} vocabulary words in a concise ~60-80 word story
- INTEGRATE ALL {word_count} target words naturally into the story text
- For each target word in the story, wrap it in **bold**: **word** (বাংলা অর্থ)
- CRITICAL: Bangla translations MUST be 2-4 words ONLY. Examples:
    GOOD → **Conciliatory** (সমঝোতামূলক মনোভাব)
    GOOD → **Cryptic** (গূঢ় বা অস্পষ্ট)
    BAD  → **Conciliatory** (সমঝোতামূলক ভাব বা পারস্পরিক আপসের মনোভাব)
- Start with a scroll-stopping hook that includes target words
- End with a question to drive engagement
- Sound like a real person, NOT AI
- Keep it to 1 short paragraph
- Make sure the story flows naturally around the vocabulary words
- Keep total content (hook + story + question) under 220 words for slide readability

Return ONLY valid JSON:
{{
  "hook_line": "Hook with **bold** words",
  "paragraphs": ["Single paragraph story with ALL target words integrated..."],
  "used_words": ["word1", "word2", "word3"],
  "debate_question": "Engaging question in Bangla+English",
  "fun_fact": "Quick interesting fact in Bangla"
}}"""


LONG_PROMPT = """You are a Bangladeshi content creator for StoryVocabs — a vocabulary learning app. Write a DETAILED, engaging social media post about a news topic.

NEWS TOPIC:
Headline: {news_title}
Details: {news_summary}

TARGET WORDS (you MUST use ALL of them naturally in the story):
{word_list}

{revision_note}

STORY ANGLE: {story_angle}

RULES:
- Write about {word_count} vocabulary words in a ~160-200 word detailed story
- INTEGRATE ALL {word_count} target words naturally into the story text
- For each target word in the story, wrap it in **bold**: **word** (বাংলা অর্থ)
- CRITICAL: Bangla translations MUST be 2-4 words ONLY. Examples:
    GOOD → **Emaciate** (শীর্ণকায় বা দুর্বল)
    GOOD → **Accord** (চুক্তি বা সম্মতি)
    BAD  → **Accord** (একমত্য বা সম্মতি, বিশেষ করে একটি আনুষ্ঠানিকভাবে পৌঁছানো বা স্পষ্টভাবে প্রকাশিত...)
- Start with a scroll-stopping hook that includes target words
- End with a thought-provoking question in Bangla
- Sound like a real person, NOT AI
- 2 paragraphs with depth and analysis
- Make sure the story flows naturally around the vocabulary words
- Keep the topic consistent throughout
- Keep total content (hook + story + question) under 300 words for slide readability

Return ONLY valid JSON:
{{
  "hook_line": "Hook with **bold** words",
  "paragraphs": ["Paragraph 1 with integrated words...", "Paragraph 2 with more words...", "Paragraph 3 with final words..."],
  "used_words": ["word1", "word2", "word3", "word4", "word5"],
  "debate_question": "Engaging question in Bangla+English",
  "fun_fact": "Quick interesting fact in Bangla"
}}"""


LONG_PROMPT_BN = """আপনি StoryVocabs-এর একজন বাংলাদেশি কন্টেন্ট ক্রিয়েটর। সামাজিক মাধ্যমে প্রকাশের জন্য বাংলায় লেখা একটি বিশদ বিশ্লেষণমূলক পোস্ট তৈরি করুন।

সাম্প্রতিক খবর:
শিরোনাম: {news_title}
বিস্তারিত: {news_summary}

লক্ষ্য শব্দ (সবগুলো অবশ্যই গল্পে ব্যবহার করতে হবে):
{word_list}

{revision_note}

গল্পের দৃষ্টিভঙ্গি: {story_angle}

নিয়মমালা:
- সম্পূর্ণ গল্পটি বাংলায় লিখুন (~160-200 শব্দ)
- লক্ষ্য ইংরেজি শব্দগুলো ইংরেজিতেই রাখুন (বোল্ড করুন), কিন্তু পাশে বাংলা অর্থ দিন
- প্রতিটি শব্দের ক্ষেত্রে: **Word** (বাংলা অর্থ)
- বাংলা অর্থ সর্বাধিক ২-৪টি শব্দের মধ্যে রাখুন
  ভালো দেখানো: **Ponderous** (ভারী বা ধীরগতি)
  ভালো দেখানো: **Accord** (চুক্তি বা সম্মতি)
- শুরুতে একটি আকর্ষণীয় হুক দিয়ে শুরু করুন
- শেষে পাঠককে ভাবাতে পারে এমন একটি প্রশ্ন দিয়ে শেষ করুন
- স্ত্বাভাবিক ভাষায় লিখুন, AI নয়
- ২টি অনুচ্ছেদে লিখুন
- মোট কন্টেন্ট ৩০০ শব্দের মধ্যে রাখুন

শুধুমাত্র valid JSON রিটার্ন করুন:
{{
  "hook_line": "বাংলায় হুক, বোল্ড **ইংরেজি শব্দ** সহ",
  "paragraphs": ["বাংলা অনুচ্ছেদ ১...", "বাংলা অনুচ্ছেদ ২..."],
  "used_words": ["word1", "word2", "word3", "word4", "word5"],
  "debate_question": "বাংলায় প্রশ্ন",
  "fun_fact": "বাংলায় তথ্য"
}}"""


QUALITY_PROMPT = """Rate this Bangladeshi social media vocabulary post.

CONTENT:
Hook: {hook}
Story: {story}
Words: {words_used}

Rate 1-10 on:
1. Human-written feel (non-AI tone)
2. Topic coverage and clarity
3. Word usage naturalness (not forced — each word belongs in this story)
4. Bangla-English readability
5. Exam usefulness
6. Content length appropriateness (not too long for slides)

IMPORTANT: 
- If ANY target word feels forced or unnatural in context, deduct 2 points per word.
- If total content (hook + story + question) exceeds 350 words, rate below 5.0 and flag as "too_long".
- A story where ALL words feel genuinely natural should score 8+.

Return ONLY JSON:
{{"overall": 7.5, "pass": true, "issues": ["issue1"], "forced_words": ["word_that_felt_forced"]}}

PASS threshold: {threshold}"""


def build_word_list(words):
    lines = []
    for i, w in enumerate(words, 1):
        lines.append(
            f"{i}. **{w['word']}** ({w.get('partOfSpeech', '')}) "
            f"— Bangla: {w['bangla']} "
            f"— Meaning: {w.get('meaning', '')}"
        )
    return "\n".join(lines)


def get_story_angle(session):
    """Return story angle instruction for this session."""
    return STORY_ANGLES.get(session, STORY_ANGLES[1])


def generate_short_post(news_title, news_summary, words, category, session=1):
    """Generate a short post (3 words)."""
    word_list = build_word_list(words)
    angle = get_story_angle(session)
    prompt = SHORT_PROMPT.format(
        news_title=news_title,
        news_summary=news_summary,
        word_list=word_list,
        word_count=len(words),
        story_angle=angle,
    )
    return call_llm([
        {"role": "system", "content": f"You write Bangla+English social media posts about {category}. {angle} Return valid JSON only."},
        {"role": "user", "content": prompt},
    ], temperature=0.8, max_tokens=1500)


def generate_long_post(news_title, news_summary, words, category, revision_words=None, language="english", session=1):
    """Generate a long post (5 words). language='bangla' for Post 2 & 4."""
    word_list = build_word_list(words)
    angle = get_story_angle(session)
    revision_note = ""
    if revision_words:
        rev_names = ", ".join(w['word'] for w in revision_words)
        revision_note = f"REVISION NOTE: These words appeared in an earlier post today: {rev_names}. Naturally re-use them in this expanded version to reinforce learning."
        if language == "bangla":
            revision_note = f"নোট: এই শব্দগুলো আজ আগে ব্যবহার হয়েছিল: {rev_names}। এগুলো এই পোস্টেও স্বাভাবিকভাবে ব্যবহার করুন।"

    prompt_template = LONG_PROMPT_BN if language == "bangla" else LONG_PROMPT
    prompt = prompt_template.format(
        news_title=news_title,
        news_summary=news_summary,
        word_list=word_list,
        word_count=len(words),
        revision_note=revision_note,
        story_angle=angle,
    )
    sys_msg = (
        f"বাংলায় সামাজিক মাধ্যম পোস্ট লিখুন {category} বিষয়ে। {angle} শুধু JSON রিটার্ন করুন।"
        if language == "bangla"
        else f"You write Bangla+English social media posts about {category}. {angle} Return valid JSON only."
    )
    return call_llm([
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": prompt},
    ], temperature=0.8, max_tokens=2500)


def quality_check(story_data, words, threshold=QUALITY_PASS_THRESHOLD):
    """Fast quality heuristic to save LLM calls; raises score if basic criteria met."""
    text = story_data.get("full_story", "") + " " + story_data.get("hook_line", "")
    text_lower = text.lower()
    
    # Check all target words are present in the story
    missing = [w["word"] for w in words if w["word"].lower() not in text_lower]
    
    # Check length
    word_count = len(text.split())
    
    if missing:
        return {"overall": 5.0, "pass": False, "issues": [f"Missing words: {missing}"], "forced_words": missing}
    if word_count < 40:
        return {"overall": 5.0, "pass": False, "issues": ["Story too short"], "forced_words": []}
    if not story_data.get("debate_question") or len(story_data.get("debate_question", "")) < 10:
        return {"overall": 6.5, "pass": False, "issues": ["No debate question"], "forced_words": []}
    
    return {"overall": 8.0, "pass": True, "issues": [], "forced_words": []}


def classify_category(news):
    """Classify news into a category."""
    text = (news.get("title", "") + " " + news.get("summary", "")).lower()
    mapping = {
        "Politics & Governance": ["politic", "parliament", "government", "minister", "election", "law", "court", "reform", "charter", "vote", "democracy"],
        "Economy & Banking": ["bank", "economy", "trade", "budget", "inflation", "export", "dollar", "taka", "gdp", "gold", "price", "payment", "finance"],
        "Sports": ["cricket", "football", "match", "win", "tournament", "player", "team", "score", "odi", "t20", "test", "bangladesh cricket", "fizz", "wicket", "mumbai", "rout"],
        "Science & Technology": ["technology", "digital", "ai", "internet", "app", "startup", "innovation", "software", "5g", "robot", "tech"],
        "Environment": ["flood", "cyclone", "climate", "environment", "river", "disaster", "energy crisis", "renewable"],
        "Society": ["student", "university", "exam", "education", "protest", "bcs", "bank job", "admission"],
    }
    bn = {"Politics & Governance": "রাজনীতি", "Economy & Banking": "অর্থনীতি", "Sports": "খেলাধুলা",
          "Science & Technology": "প্রযুক্তি", "Environment": "পরিবেশ", "Society": "সমাজ"}
    best, best_score = "General Knowledge", 0
    for cat, kws in mapping.items():
        s = sum(1 for k in kws if k in text)
        if s > best_score:
            best_score, best = s, cat
    if "cricket" in text or "fizz" in text or "wicket" in text:
        best = "Sports"
    return {"en": best, "bn": bn.get(best, "সাধারণ জ্ঞান")}


def build_post_content(story_data, words, news, date_str, post_label, style, session=1):
    """Build standardized post content dict with quality check."""
    story_data["full_story"] = " ".join(story_data.get("paragraphs", []))

    qc = quality_check(story_data, words)
    score = qc.get("overall", 6.0) if qc else 6.0
    passed = qc.get("pass", score >= QUALITY_PASS_THRESHOLD) if qc else (score >= QUALITY_PASS_THRESHOLD)
    forced = qc.get("forced_words", []) if qc else []
    needs_review = not passed

    if needs_review:
        print(f"   ⚠ Quality Score: {score}/10 — BELOW THRESHOLD ({QUALITY_PASS_THRESHOLD}) — flagged needs_review")
        if forced:
            print(f"   ⚠ Forced words detected: {', '.join(forced)}")
    else:
        print(f"   ✓ Quality Score: {score}/10 — PASS")

    used_names = story_data.get("used_words", [])
    final_words = []
    for name in used_names:
        for w in words:
            if w["word"].lower() == name.lower():
                final_words.append(dict(w))
                break
    if not final_words:
        final_words = words[:len(used_names)] if used_names else words[:3]

    category = classify_category(news)

    return {
        "post_label": post_label,
        "style": style,
        "session": session,
        "hook_line": story_data.get("hook_line", ""),
        "paragraphs": story_data.get("paragraphs", []),
        "full_story": story_data.get("full_story", ""),
        "words": final_words,
        "word_count": len(final_words),
        "debate_question": story_data.get("debate_question", ""),
        "fun_fact": story_data.get("fun_fact", ""),
        "quality_score": score,
        "needs_review": needs_review,
        "forced_words": forced,
        "category": category,
        "source_title": news.get("title", ""),
        "date": date_str,
    }


def generate_post_with_retry(generate_fn, words, news, date_str, post_label, style, session, max_retries=2):
    """Generate a post and retry once if quality is below threshold."""
    story_data = generate_fn()
    if not story_data:
        for _ in range(max_retries):
            time.sleep(2)
            story_data = generate_fn()
            if story_data:
                break

    if not story_data:
        return None

    content = build_post_content(story_data, words, news, date_str, post_label, style, session)

    # Retry once if quality fails
    if content["needs_review"] and max_retries > 0:
        print("   Retrying for quality improvement...")
        time.sleep(2)
        retry_data = generate_fn()
        if retry_data:
            retry_content = build_post_content(retry_data, words, news, date_str, post_label, style, session)
            if retry_content["quality_score"] > content["quality_score"]:
                print(f"   Retry improved score: {content['quality_score']} → {retry_content['quality_score']}")
                content = retry_content

    return content


def generate_all_posts(word_sets, news_stories, date_str, session=1):
    """Generate all 4 posts for the day.

    Args:
        word_sets: dict from select_words_for_session() or positional fallback.
        news_stories: list of 2 news dicts (topic A for posts 1-2, topic B for posts 3-4).
        date_str: YYYY-MM-DD
        session: Session number (1-4) for angle injection and tracking.

    Returns:
        dict with post_1, post_2, post_3, post_4 content
    """
    results = {}
    tracker = load_tracker()
    all_used_words = []

    news_a = news_stories[0]
    news_b = news_stories[1]

    topic_a_label = classify_category(news_a)
    topic_b_label = classify_category(news_b)

    angle = get_story_angle(session)
    print(f"\n  Story angle (Session {session}): {angle}")

    # ─── POST 1: Short, 3 words, Story A ───────────────────────────────────
    print("\n  ┌─ Post 1: Quick Bite (3 words, Story A)")
    story_a_title = news_a.get("title", "Today's Topic")
    story_a_summary = news_a.get("summary", "")

    def gen_post1():
        return generate_short_post(story_a_title, story_a_summary,
                                   word_sets["post_1_words"], topic_a_label["en"], session)

    content1 = generate_post_with_retry(gen_post1, word_sets["post_1_words"],
                                        news_a, date_str, "Post 1 — Quick Bite", "short", session)
    if content1:
        results["post_1"] = content1
        all_used_words.extend(content1["words"])
    else:
        results["post_1"] = make_fallback(word_sets["post_1_words"], news_a, date_str, "Post 1 — Quick Bite", "short", session)

    # ─── POST 2: Long, 5 words (3 revise + 2 new), Story A, BANGLA ─────────
    print("\n  ┌─ Post 2: Deep Dive — Bangla Story (5 words, Story A)")

    def gen_post2():
        return generate_long_post(story_a_title, story_a_summary,
                                  word_sets["post_2_words"], topic_a_label["en"],
                                  revision_words=word_sets["post_1_words"][:3],
                                  language="bangla", session=session)

    content2 = generate_post_with_retry(gen_post2, word_sets["post_2_words"],
                                        news_a, date_str, "Post 2 — Deep Dive", "long", session)
    if content2:
        results["post_2"] = content2
        all_used_words.extend(content2["words"])
    else:
        results["post_2"] = make_fallback(word_sets["post_2_words"], news_a, date_str, "Post 2 — Deep Dive", "long", session)

    # ─── POST 3: Short, 3 words, Story B ───────────────────────────────────
    print("\n  ┌─ Post 3: Quick Bite (3 words, Story B)")
    story_b_title = news_b.get("title", "Another Topic Today")
    story_b_summary = news_b.get("summary", "")

    def gen_post3():
        return generate_short_post(story_b_title, story_b_summary,
                                   word_sets["post_3_words"], topic_b_label["en"], session)

    content3 = generate_post_with_retry(gen_post3, word_sets["post_3_words"],
                                        news_b, date_str, "Post 3 — Quick Bite", "short", session)
    if content3:
        results["post_3"] = content3
        all_used_words.extend(content3["words"])
    else:
        results["post_3"] = make_fallback(word_sets["post_3_words"], news_b, date_str, "Post 3 — Quick Bite", "short", session)

    # ─── POST 4: Long, 5 words (3 revise + 2 new), Story B, BANGLA ─────────
    print("\n  ┌─ Post 4: Deep Dive — Bangla Story (5 words, Story B)")

    def gen_post4():
        return generate_long_post(story_b_title, story_b_summary,
                                  word_sets["post_4_words"], topic_b_label["en"],
                                  revision_words=word_sets["post_3_words"][:3],
                                  language="bangla", session=session)

    content4 = generate_post_with_retry(gen_post4, word_sets["post_4_words"],
                                        news_b, date_str, "Post 4 — Deep Dive", "long", session)
    if content4:
        results["post_4"] = content4
        all_used_words.extend(content4["words"])
    else:
        results["post_4"] = make_fallback(word_sets["post_4_words"], news_b, date_str, "Post 4 — Deep Dive", "long", session)

    # Dedup and track all unique words (1 count per word per date)
    unique_words = list({w["word"].lower(): w for w in all_used_words}.values())
    tracker = mark_used(tracker, unique_words, date_str)
    save_tracker(tracker)
    print(f"\n   Tracked {len(unique_words)} unique words for {date_str}")

    return results


def make_fallback(words, news, date_str, label, style, session=1):
    """Create fallback post if AI generation fails."""
    return {
        "post_label": label,
        "style": style,
        "session": session,
        "hook_line": news.get("title", ""),
        "paragraphs": [news.get("summary", "")[:200]],
        "full_story": news.get("summary", "")[:200],
        "words": words,
        "word_count": len(words),
        "debate_question": "তোমার মতামত কী?",
        "fun_fact": "",
        "quality_score": 5.0,
        "needs_review": True,
        "forced_words": [],
        "category": classify_category(news),
        "source_title": news.get("title", ""),
        "date": date_str,
    }
