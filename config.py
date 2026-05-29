import os
from dotenv import load_dotenv

load_dotenv()

# Load all GROQ_API_KEYs from environment variables
GROQ_API_KEYS = []
for i in range(1, 10):
    key = os.getenv(f"GROQ_API_KEY_{i}")
    if key:
        GROQ_API_KEYS.append(key)

# Add legacy key if present
legacy_key = os.getenv("GROQ_API_KEY")
if legacy_key and legacy_key not in GROQ_API_KEYS:
    GROQ_API_KEYS.append(legacy_key)
GROQ_MODEL = "llama-3.3-70b-versatile"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ─── PRIMARY MODEL ────────────────────────────────────────────────────────────
# Qwen3 Next 80B A3B Instruct — best Bangla+English, 262K context, strong JSON
# Confirmed model ID from OpenRouter: qwen/qwen3-next-80b-a3b-instruct:free
OPENROUTER_MODEL = "qwen/qwen3-next-80b-a3b-instruct:free"

# ─── ALTERNATIVES (uncomment to switch) ──────────────────────────────────────
# Google Gemma 4 31B — newest (Apr 2026), great multilingual, 262K context
OPENROUTER_FALLBACK_MODEL = "google/gemma-4-31b:free"

# NVIDIA Nemotron 3 Nano 30B A3B — highest throughput, best for batch runs
# OPENROUTER_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Primary API: OpenRouter (Qwen3 Next 80B — best Bangla support)
# Fallback: Groq (Llama 3.3 70B)
USE_OPENROUTER_AS_PRIMARY = True

BRAND = {
    "primary_blue": "#3b82f6",
    "primary_purple": "#8b5cf6",
    "bg_color": "#f8fafc",
    "text_primary": "#111827",
    "text_secondary": "#6b7280",
    "text_muted": "#9ca3af",
    "gradient": "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
    "font_family": "'Inter', 'Noto Sans Bengali', sans-serif",
}

# ─── GENRE SCHEDULE ─────────────────────────────────────────
# 0=Monday, 1=Tuesday, ..., 6=Sunday
# Wednesday (2) = OFF DAY

GENRE_SCHEDULE = {
    0: {  # Monday
        "genres": ["technology", "business"],
        "label": "প্রযুক্তি ও ব্যবসা",
        "keywords": [
            "technology", "digital", "ai", "internet", "app", "startup",
            "innovation", "software", "5g", "robot", "tech", "online",
            "business", "trade", "economy", "market", "company",
            "startup", "entrepreneur", "investment", "export", "import",
            "rmg", "garment", "bank", "finance", "stock", "payment",
        ],
        "queries": [
            "Bangladesh technology digital",
            "Bangladesh business economy trade",
            "Bangladesh startup innovation",
            "Bangladesh banking finance",
            "Bangladesh tech companies",
        ],
    },
    1: {  # Tuesday
        "genres": ["technology", "business"],
        "label": "প্রযুক্তি ও ব্যবসা",
        "keywords": [
            "technology", "digital", "ai", "internet", "app", "startup",
            "innovation", "software", "5g", "robot", "tech", "online",
            "business", "trade", "economy", "market", "company",
            "startup", "entrepreneur", "investment", "export", "import",
            "rmg", "garment", "bank", "finance", "stock", "payment",
        ],
        "queries": [
            "Bangladesh technology latest",
            "Bangladesh business today",
            "Bangladesh economy trade",
            "Bangladesh digital payment",
            "Bangladesh startup news",
        ],
    },
    2: {  # Wednesday — editorial on business/technology
        "genres": ["business", "technology"],
        "label": "ব্যবসা ও প্রযুক্তি (সম্পাদকীয়)",
        "keywords": [
            "business", "trade", "economy", "market", "company",
            "startup", "entrepreneur", "investment", "export", "import",
            "rmg", "garment", "bank", "finance", "stock", "payment",
            "technology", "digital", "ai", "internet", "app", "startup",
            "innovation", "software", "5g", "robot", "tech", "online",
            "editorial", "analysis",
        ],
        "queries": [
            "Bangladesh business editorial analysis",
            "Bangladesh technology trending",
            "Bangladesh economy business news today",
            "Bangladesh digital innovation",
            "Bangladesh business trade latest",
        ],
    },
    3: {  # Thursday
        "genres": ["politics", "cricket", "history"],
        "label": "রাজনীতি ও ক্রিকেট",
        "keywords": [
            "politic", "parliament", "government", "minister", "election",
            "vote", "democracy", "law", "court", "reform", "charter",
            "cricket", "football", "match", "win", "tournament", "player",
            "team", "score", "odi", "t20", "test", "bangladesh cricket",
            "history", "heritage", "culture", "independence", "liberation",
            "geopolitic", "foreign", "diplomat", "border", "india", "china",
        ],
        "queries": [
            "Bangladesh politics government",
            "Bangladesh cricket match",
            "Bangladesh politics reform",
            "Bangladesh cricket tournament",
            "Bangladesh geopolitics history",
        ],
    },
    4: {  # Friday
        "genres": ["politics", "cricket", "geopolitics"],
        "label": "রাজনীতি ও ক্রিকেট",
        "keywords": [
            "politic", "parliament", "government", "minister", "election",
            "vote", "democracy", "law", "court", "reform", "charter",
            "cricket", "football", "match", "win", "tournament", "player",
            "team", "score", "odi", "t20", "test", "bangladesh cricket",
            "history", "heritage", "culture", "independence", "liberation",
            "geopolitic", "foreign", "diplomat", "border", "india", "china",
        ],
        "queries": [
            "Bangladesh politics latest",
            "Bangladesh cricket today",
            "Bangladesh geopolitics",
            "Bangladesh government reform",
            "Bangladesh cricket score",
        ],
    },
    5: {  # Saturday
        "genres": ["politics", "cricket", "history"],
        "label": "রাজনীতি, ক্রিকেট ও ইতিহাস",
        "keywords": [
            "politic", "parliament", "government", "minister", "election",
            "vote", "democracy", "law", "court", "reform", "charter",
            "cricket", "football", "match", "win", "tournament", "player",
            "team", "score", "odi", "t20", "test", "bangladesh cricket",
            "history", "heritage", "culture", "independence", "liberation",
            "geopolitic", "foreign", "diplomat", "border", "india", "china",
        ],
        "queries": [
            "Bangladesh politics",
            "Bangladesh cricket news",
            "Bangladesh history culture",
            "Bangladesh geopolitics",
            "Bangladesh reform election",
        ],
    },
    6: {  # Sunday — editorial on politics/geopolitics
        "genres": ["politics", "geopolitics"],
        "label": "রাজনীতি ও ভূ-রাজনীতি (সম্পাদকীয়)",
        "keywords": [
            "politic", "parliament", "government", "minister", "election",
            "vote", "democracy", "law", "court", "reform", "charter",
            "geopolitic", "foreign", "diplomat", "border", "india", "china",
            "usa", "united nations", "rohingya", "treaty", "alliance",
            "sovereignty", "foreign policy", "bilateral", "summit",
            "editorial", "analysis", "opinion piece",
        ],
        "queries": [
            "Bangladesh politics editorial analysis",
            "Bangladesh geopolitics foreign policy",
            "Bangladesh politics reform trending",
            "Bangladesh geopolitics India China",
            "Bangladesh politics news today",
        ],
    },
}

NEWS_SOURCES = [
    "https://www.thedailystar.net/rss.xml",
    "https://www.dhakatribune.com/rss",
    "https://bdnews24.com/rss",
    "https://en.prothomalo.com/rss",
    "https://www.tbsnews.net/rss",
    "https://www.thefinancialexpress-bd.com/rss",
]

# Canvas size: 1080×1350 (4:5 portrait for Instagram Reels, Stories, etc.)
CANVAS = (1080, 1350)

# ─── DAILY POST SCHEDULE ──────────────────────────────────
# 4 posts per day, 2 different stories/topics
# Post 1: 3 words, new story (Topic A)
# Post 2: 5 words (3 revise from Post 1 + 2 new), Topic A
# Post 3: 2 words, new story (Topic B - different)
# Post 4: 5 words (2 revise from Post 3 + 3 new), Topic B
# Total: 10 unique words/day

POST_SCHEDULE = {
    "post_1": {
        "label": "Post 1 — Quick Bite",
        "word_count": 3,
        "style": "short",
        "target_words": 80,
        "description": "3 words, short punchy story",
    },
    "post_2": {
        "label": "Post 2 — Deep Dive",
        "word_count": 5,
        "style": "long",
        "target_words": 150,
        "revise_from": "post_1",
        "revise_count": 3,
        "new_count": 2,
        "description": "3 revised + 2 new, expanded story",
    },
    "post_3": {
        "label": "Post 3 — Quick Bite",
        "word_count": 2,
        "style": "short",
        "target_words": 80,
        "description": "2 words, short story on different topic",
    },
    "post_4": {
        "label": "Post 4 — Deep Dive",
        "word_count": 5,
        "style": "long",
        "target_words": 150,
        "revise_from": "post_3",
        "revise_count": 2,
        "new_count": 3,
        "description": "2 revised + 3 new, expanded story",
    },
}

# Words needed per day: 3 + 2 + 2 + 3 = 10 unique
WORDS_PER_DAY = 10

# ─── CAPTION ROTATION SYSTEM ────────────────────────────────────
CAPTION_TAGLINES = [
    "📌 আজকের খবরের হেডলাইন থেকে বাছাই করা {word_count}টি গুরুত্বপূর্ণ Vocabulary:",
    "💡 Vocabulary মুখস্থ করে ভুলে যাচ্ছেন? আজকের নিউজ থেকে পড়ে নিন {word_count}টি নতুন শব্দ:",
    "📰 শুধুমাত্র নিউজ পড়েই যদি Vocabulary শেখা যায়, তবে মুখস্থ করবেন কেন? চলুন দেখি আজকের {word_count}টি শব্দ:",
    "🎯 Daily News থেকে Vocabulary শেখার সবচেয়ে সহজ উপায়। আজকের আয়োজনে থাকছে {word_count}টি গুরুত্বপূর্ণ শব্দ:",
    "✨ খবরের প্রেক্ষাপট থেকে শব্দ শিখলে তা সহজে ভোলা যায় না। দেখে নিন আজকের খবরের {word_count}টি শব্দ:",
    "🚀 BCS বা Bank Job-এর প্রস্তুতিতে Vocabulary নিয়ে চিন্তায় আছেন? নিউজ থেকে শিখুন এই {word_count}টি শব্দ:",
    "🔥 প্রতিদিনের খবরের মাঝেই লুকিয়ে থাকে দারুণ সব ইংরেজি শব্দ! চলুন দেখে নিই আজকের {word_count}টি শব্দ:",
    "📚 মুখস্থ না করে গল্পের ছলে Vocabulary শেখার আজকের আয়োজনে থাকছে {word_count}টি শব্দ:"
]

CAPTION_PROOF_LINES = [
    "✅ BCS, Bank Job কিংবা IELTS — যেকোনো প্রতিযোগিতামূলক পরীক্ষায় এই শব্দগুলো বারবার আসে এবং দারুণ কাজে দেয়।",
    "✅ News article বা Editorial পড়তে গেলে এই শব্দগুলো প্রায়ই চোখে পড়বে আপনার। অর্থ না জানলে পুরো প্যারাগ্রাফের মিনিং হারাবেন।",
    "✅ সাধারণ ইংরেজির চেয়ে এই শব্দগুলো আপনার স্পোকেন বা রাইটিং ইংলিশকে আরও একটু standard ও প্রফেশনাল করে তুলবে।",
    "✅ বিগত বছরগুলোর Competitive Exam-এর প্রশ্ন ঘাঁটলে দেখা যায়, এই শব্দগুলোর ব্যবহার প্রচুর! তাই এগুলো এড়িয়ে যাওয়ার সুযোগ নেই।",
    "✅ Newspaper-এর Editorial section বুঝতে এবং Reading skill বাড়াতে এই ধরনের Advance Vocabulary জানা থাকা ভীষণ জরুরি।",
    "✅ সাধারণ ইংরেজির চেয়ে এই স্মার্ট শব্দগুলো আপনার লেখনি বা বলায় প্রফেশনালিজমের ছোঁয়া নিয়ে আসবে।",
    "✅ হাজার হাজার শব্দ মুখস্থ করার চেয়ে, প্রতিদিনের খবর থেকে এমন কার্যকরী ও বাছাইকৃত শব্দ শেখা অনেক বেশি প্রাসঙ্গিক।",
    "✅ IELTS-এর Lexical Resource-এ ভালো ব্যান্ড স্কোর তুলতে এই শব্দগুলো আপনাকে অন্যদের চেয়ে নিশ্চিতভাবেই এগিয়ে রাখবে।"
]

CAPTION_SCIENCE_HOOKS = [
    "🧠 গবেষণায় দেখা গেছে, রট মুখস্থ করার চেয়ে কোনো context বা গল্পের সাথে মিলিয়ে শব্দ শিখলে তা ৫ গুণ বেশি মনে থাকে।",
    "💡 আমাদের মস্তিষ্ক বিচ্ছিন্ন শব্দের চেয়ে কোনো ঘটনার সাথে জুড়ে থাকা শব্দ বেশি মনে রাখতে পারে। StoryVocabs ঠিক এই পদ্ধতিতেই কাজ করে।",
    "🎯 Spaced Repetition এবং Contextual Learning-এর দারুণ এক সমন্বয় পাবেন StoryVocabs-এ; যাতে একবার শেখা শব্দ আর কখনো ভুলতে না হয়।",
    "🚀 Context ছাড়া Vocabulary শেখা আর পানি ছাড়া সাঁতার শেখার মতোই কঠিন। তাই আমরা প্রতিদিনের খবরের মাঝেই শব্দগুলো গেঁথে দিই।",
    "⚙️ হার্ভার্ড ইউনিভার্সিটির এক গবেষণায় প্রমাণিত—গল্পের আদলে পড়া শব্দ দীর্ঘস্থায়ী মেমোরিতে সহজে জায়গা করে নেয়। একদম মুখস্থ ছাড়াই!",
    "✨ Vocabulary শেখার পুরনো পদ্ধতি বদলে ফেলুন। Real-life news context-এর মাধ্যমে শিখলে রিভিশন ছাড়াই অনেকদিন মনে থাকে।",
    "📖 কোনো শব্দ কোন বাক্যে কীভাবে ব্যবহৃত হচ্ছে তা না জানলে এর আসল অর্থ বোঝা কঠিন। আমাদের পদ্ধতি আপনাকে ঠিক সেটাই বুঝতে সাহায্য করে।",
    "🧠 মুখস্থবিদ্যার দিন শেষ! এখন থেকে শব্দ শিখুন বাস্তব ঘটনার প্রেক্ষাপটে, যাতে পরীক্ষায় সঠিক মুহূর্তে ঠিক মনে পড়ে যায়।"
]

CAPTION_CTA_BLOCKS = [
    "👇 আজকের আয়োজনের কোন শব্দটি আপনার কাছে একেবারেই নতুন ছিল? কমেন্টে লিখে জানাতে পারেন।\n💾 পরবর্তীতে রিভিশন দেয়ার জন্য পোস্টটি Save করে রাখতে ভুলবেন না!\n\n👉 storyvocabs.vercel.app — Learn naturally, retain permanently.",
    "📲 আপনার Vocabulary জার্নিকে আরও সহজ ও আনন্দদায়ক করতে আজই ভিজিট করুন আমাদের ওয়েবসাইটে:\n🔗 storyvocabs.vercel.app (লিঙ্ক বায়ো-তে দেয়া আছে)",
    "💡 এই শব্দগুলো দিয়ে আপনি নিজে একটি বাক্য তৈরি করতে পারবেন? আপনার চেষ্টাটুকু কমেন্টে শেয়ার করুন আমাদের সাথে!\n\n🔥 Get Premium — unlimited stories & zero ads: storyvocabs.vercel.app",
    "📌 প্রতিদিন এমন দারুণ সব Vocabulary শিখতে আমাদের পেইজে চোখ রাখুন।\n📤 আপনার যে বন্ধুটি Vocabulary নিয়ে সংগ্রাম করছে, তাকে মেনশন বা শেয়ার করে দিন!\n\n👉 Website: storyvocabs.vercel.app",
    "🚀 StoryVocabs-এর সাথে Vocabulary শেখা হোক সম্পূর্ণ ন্যাচারাল এবং দীর্ঘস্থায়ী।\n✨ ৫০০+ খবরের গল্প এবং এক্সাম প্যাক পেতে আমাদের Premium সাবস্ক্রিপশনটি দেখে নিতে পারেন: storyvocabs.vercel.app",
    "💬 আপনি কি এর আগে এই শব্দগুলোর অর্থ জানতেন? নিচে কমেন্ট করে আপনার মতামত দিন।\n💾 পরীক্ষার আগের রাতে চোখ বুলানোর জন্য পোস্টটি প্রোফাইলে Save করে রাখুন।\n\n👉 App Link: storyvocabs.vercel.app",
    "🎯 এভাবেই প্রতিদিনের খবর থেকে প্রয়োজনীয় সব ইংরেজি শব্দ শিখতে আমাদের সাথেই থাকুন।\n👉 Get Unlimited Stories & Exam Packs: storyvocabs.vercel.app",
    "🧠 আজকের শব্দগুলো নোটবুকে লিখে রাখতে পারেন অথবা পোস্টটি বুকমার্ক করে রাখতে পারেন।\n📲 রেগুলার আপডেটের জন্য আমাদের ফলো দিয়ে রাখুন।\n\n🔗 storyvocabs.vercel.app — Learn naturally, retain permanently."
]

def get_caption(style, word_count, title, category_icon, category_bn, hashtags, revise_count, new_count, post_number, session_number, day_number):
    idx = (post_number + session_number + day_number) % 8
    
    tagline = CAPTION_TAGLINES[idx].format(word_count=word_count)
    proof_line = CAPTION_PROOF_LINES[idx]
    science_hook = CAPTION_SCIENCE_HOOKS[idx]
    cta_block = CAPTION_CTA_BLOCKS[idx]

    middle_block = ""
    if style == "long":
        middle_block = f"🔁 {revise_count}টি আগের শব্দ রিভিশন + {new_count}টি নতুন শব্দ\n→ Spaced Repetition পদ্ধতিতে শব্দ মনে রাখো, আর কখনো ভুলবে না!\n\n"

    caption = f"""{tagline}

📖 {title}
{category_icon} বিভাগ: {category_bn}

{middle_block}{proof_line}
{science_hook}

{cta_block}

{hashtags}
"""
    return caption

HASHTAG_POOL = [
    "#StoryVocabs", "#বাংলাদেশ", "#BCS", "#BankJob",
    "#EnglishVocabulary", "#শব্দেরগল্প", "#vocab", "#IELTS",
    "#পরীক্ষারপ্রস্তুতি", "#currentaffairs", "#GK",
    "#Admission", "#IBA", "#EnglishLearning", "#wordoftheday",
    "#খবরেশব্দ", "#পড়োখবরশেখোশব্দ", "#vocabulary",
    "#বিসিএস", "#ব্যাংকচাকরি", "#শব্দভান্ডার",
    "#Noun", "#Verb", "#Adjective", "#Adverb",
    "#LearnEnglish", "#EnglishForBCS", "#VocabularyBuilder",
    "#DailyVocab", "#StoryBasedLearning",
]
