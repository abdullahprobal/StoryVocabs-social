"""Quick test to verify OpenRouter model ID is correct."""
import sys, requests
sys.stdout.reconfigure(encoding="utf-8")
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL

print(f"Testing model: {OPENROUTER_MODEL}")
resp = requests.post(
    f"{OPENROUTER_BASE_URL}/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://storyvocabs.vercel.app",
        "X-Title": "StoryVocabs Social",
        "Content-Type": "application/json",
    },
    json={
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": 'Reply with exactly: {"status": "ok"}'}],
        "temperature": 0.1,
        "max_tokens": 30,
    },
    timeout=30,
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print(f"Response: {content}")
    print("OpenRouter connection: OK")
else:
    print(f"Error body: {resp.text[:500]}")
