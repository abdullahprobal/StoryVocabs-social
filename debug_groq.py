"""Debug script to test Groq API."""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from config import GROQ_API_KEY, GROQ_MODEL
from groq import Groq
import json

client = Groq(api_key=GROQ_API_KEY)

test_prompt = """Write a short story in Bangla+English mix about Bangladesh politics.
Use these 5 words: Cascade, Squalor, Indifferent, Buffoon, Infrastructure.

Return ONLY valid JSON with these keys:
{
  "hook_line": "attention grabbing first line",
  "paragraphs": ["para 1", "para 2", "para 3"],
  "full_story": "all paras combined",
  "used_words": ["Cascade", "Squalor", "Indifferent", "Buffoon", "Infrastructure"],
  "debate_question": "a question in Bangla",
  "fun_fact": "a fact in Bangla"
}"""

response = client.chat.completions.create(
    model=GROQ_MODEL,
    messages=[
        {"role": "system", "content": "You are a Bangladeshi journalist. Always respond with valid JSON only. No markdown. No code blocks."},
        {"role": "user", "content": test_prompt},
    ],
    temperature=0.7,
    max_tokens=1500,
)

raw = response.choices[0].message.content.strip()
print(f"Raw response ({len(raw)} chars):")
print(raw[:500])
print("---")

# Try to parse
if raw.startswith("```"):
    raw = raw.split("\n", 1)[1]
if raw.endswith("```"):
    raw = raw.rsplit("```", 1)[0]
if raw.startswith("json"):
    raw = raw[4:]
raw = raw.strip()

try:
    parsed = json.loads(raw)
    print("\nJSON parsed successfully!")
    print(f"Hook: {parsed.get('hook_line', '')[:80]}")
    print(f"Paragraphs: {len(parsed.get('paragraphs', []))}")
    print(f"Story length: {len(parsed.get('full_story', ''))}")
except json.JSONDecodeError as e:
    print(f"\nJSON parse failed: {e}")
    print(f"Cleaned raw (first 300): {raw[:300]}")
