import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

BRAND = {
    "primary_blue": "#3b82f6",
    "primary_purple": "#8b5cf6",
    "bg_color": "#f8fafc",
    "text_primary": "#111827",
    "text_secondary": "#64748b",
    "text_muted": "#9ca3af",
    "gradient": "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
    "font_family": "'Inter', 'Noto Sans Bengali', sans-serif",
}

NEWS_SOURCES = [
    "https://www.thedailystar.net/rss.xml",
    "https://www.dhakatribune.com/rss",
    "https://bdnews24.com/rss",
]

NEWS_GOOGLE_QUERIES = [
    "Bangladesh economy today",
    "Bangladesh politics today",
    "Bangladesh science technology",
    "Bangladesh international relations",
    "Bangladesh environment climate",
]

DAILY_CATEGORIES = {
    0: {"bn": "রাজনীতি ও শাসন", "en": "Politics & Governance"},
    1: {"bn": "অর্থনীতি ও ব্যাংকিং", "en": "Economy & Banking"},
    2: {"bn": "আন্তর্জাতিক সম্পর্ক", "en": "International Relations"},
    3: {"bn": "বিজ্ঞান ও প্রযুক্তি", "en": "Science & Technology"},
    4: {"bn": "ইতিহাস ও সংস্কৃতি", "en": "History & Culture"},
    5: {"bn": "পরিবেশ ও ভূগোল", "en": "Environment & Geography"},
    6: {"bn": "সাধারণ জ্ঞান", "en": "General Knowledge"},
}

INSTAGRAM_SIZE = (1080, 1080)
FACEBOOK_SIZE = (1200, 1200)

CAPTION_TEMPLATE = """{tagline}

📖 আজকের গল্প: {title}

{category_icon} বিভাগ: {category_bn}
📝 আজকের শব্দ: {word_count}টি

{hashtags}

💾 Save করো পরে পড়ার জন্য!
📤 Share করো বন্ধুদের সাথে!
💬 Comment এ লেখো — কোন শব্দটা নতুন শিখলে?

🔗 StoryVocabs App: গল্পে শব্দ শেখো — Link in Bio
"""

HASHTAG_POOL = [
    "#storyvocabs", "#বাংলাদেশ", "#BCS", "#BankJob",
    "#EnglishVocabulary", "#শব্দেরগল্প", "#vocab", "#IELTS",
    "#পরীক্ষারপ্রস্তুতি", "#currentaffairs", "#GK",
    "#Admission", "#IBA", "#EnglishLearning", "#wordoftheday",
    "#খবরেশব্দ", "#পড়োখবরশেখোশব্দ", "#vocabulary",
    "#বিসিএস", "#ব্যাংকচাকরি", "#শব্দভান্ডার",
]
