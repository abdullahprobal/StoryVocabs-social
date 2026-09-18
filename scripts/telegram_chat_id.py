"""After messaging your bot once, prints the chat id (needs TELEGRAM_BOT_TOKEN in .env)."""
import requests

from engine import settings

r = requests.get(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates", timeout=30).json()
chats = {(m.get("message") or {}).get("chat", {}).get("id") for m in r.get("result", [])}
chats.discard(None)
print("chat ids seen:", sorted(chats) or "none yet — send the bot a message first")
