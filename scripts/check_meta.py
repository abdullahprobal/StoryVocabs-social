"""Verify Meta credentials in .env: prints Page name, IG account and token expiry. No secrets printed."""
from datetime import datetime, timezone

from engine import settings
from engine.publishers import meta

if not meta.configured():
    raise SystemExit("META_PAGE_ID / META_PAGE_TOKEN missing in .env")
print("Page:", meta.page_name(), f"(id {settings.META_PAGE_ID})")
info = meta.token_info()
exp = info.get("expires_at") or 0
print("Token type:", info.get("type"), "| scopes:", ", ".join(info.get("scopes", [])))
print("Expires:", "never" if not exp else datetime.fromtimestamp(exp, tz=timezone.utc).isoformat())
if settings.META_IG_USER_ID:
    r = meta._call("GET", f"/{settings.META_IG_USER_ID}", fields="username,followers_count")
    print("Instagram:", r.get("username"), "followers", r.get("followers_count"))
else:
    print("Instagram: not configured (PUBLISH_TO_INSTAGRAM should be false)")
