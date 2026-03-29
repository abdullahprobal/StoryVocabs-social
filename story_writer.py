"""Generates bilingual story + vocabulary using Groq AI."""

import json
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, DAILY_CATEGORIES


PROMPT_TEMPLATE = """You are a Bangladeshi exam prep content creator writing for students preparing for BCS, Bank Jobs, University Admission, IBA, and IELTS exams.

NEWS HEADLINE: {headline}
NEWS SUMMARY: {summary}
TODAY'S CATEGORY: {category_bn} ({category_en})

Your task: Write a social media post that teaches vocabulary THROUGH this news story.

RULES:
1. Write in BANGLA with ENGLISH words embedded naturally (code-switching style)
2. Put Bangla translation in parentheses after each advanced English word
3. Make it feel like a smart friend explaining current affairs
4. 150-200 words max
5. Pick 5-10 exam-relevant English words from the story
6. Be factual about the news, creative with the vocabulary teaching

Return ONLY valid JSON with these exact keys:
{{
  "title": "Short catchy title in Bangla+English mix (max 10 words)",
  "story": "The 150-200 word bilingual narrative with English words in bold markers like **word**",
  "words": [
    {{
      "word": "Inflation",
      "pronunciation": "/ɪnˈfleɪ.ʃən/",
      "bangla": "মুদ্রাস্ফীতি",
      "example": "The central bank raised rates to control inflation."
    }}
  ],
  "exam_note": "এই শব্দগুলো BCS, Bank AD, এবং Admission পরীক্ষায় ঘন ঘন আসে",
  "fun_fact": "A short 1-line interesting fact related to the topic (in Bangla)"
}}

IMPORTANT: Return ONLY the JSON object. No extra text before or after."""


def generate_content(news_data):
    """Send news to Groq and get back story + vocabulary."""
    
    client = Groq(api_key=GROQ_API_KEY)
    
    story_info = news_data.get("selected_story")
    category = news_data.get("category", DAILY_CATEGORIES[6])
    
    if not story_info:
        # Fallback: use a general topic
        headline = "Bangladesh's economic growth and development"
        summary = "Bangladesh continues to show strong economic performance with rising exports and digital transformation across sectors."
    else:
        headline = story_info.get("title", "")
        summary = story_info.get("summary", "")
    
    prompt = PROMPT_TEMPLATE.format(
        headline=headline,
        summary=summary,
        category_bn=category["bn"],
        category_en=category["en"],
    )
    
    print(f"🤖 Generating content with Groq AI...")
    
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a bilingual Bangla-English content creator for exam preparation. Always respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )
    
    raw = response.choices[0].message.content.strip()
    
    # Clean up potential markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️ JSON parse failed, using fallback content")
        content = {
            "title": headline,
            "story": f"আজকের খবরে: {headline}। {summary}",
            "words": [],
            "exam_note": "এই শব্দগুলো BCS ও Bank পরীক্ষায় আসে",
            "fun_fact": "",
        }
    
    # Add metadata
    content["category"] = category
    content["source_headline"] = headline
    content["date"] = news_data.get("date", "")
    content["word_count"] = len(content.get("words", []))
    
    print(f"✅ Generated {content['word_count']} vocabulary words")
    print(f"📝 Title: {content.get('title', '')[:60]}")
    
    return content


if __name__ == "__main__":
    from news_scraper import scrape_news
    news = scrape_news()
    content = generate_content(news)
    print(json.dumps(content, indent=2, ensure_ascii=False))
