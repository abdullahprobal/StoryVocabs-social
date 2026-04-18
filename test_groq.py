"""Test Groq fallback is working."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from story_writer import call_groq
result = call_groq(
    [{"role": "user", "content": "Reply with exactly this JSON: {\"status\": \"ok\", \"model\": \"groq\"}"}],
    temperature=0.1,
    max_tokens=30,
)
print(f"Groq fallback result: {result}")
print("Groq OK" if result else "Groq FAILED")
