"""Meta Graph API publisher: Facebook Page + Instagram Business.

Facebook carousel : N x POST /{page}/photos (published=false, url=...) → POST /{page}/feed attached_media
Facebook single   : POST /{page}/photos (url, message)
Facebook story    : POST /{page}/photo_stories (photo_id of an unpublished photo)
Instagram carousel: N x POST /{ig}/media (is_carousel_item, image_url) → POST /{ig}/media (CAROUSEL, children)
                    → POST /{ig}/media_publish
Instagram single  : POST /{ig}/media (image_url, caption) → media_publish
Instagram story   : POST /{ig}/media (image_url, media_type=STORIES) → media_publish
Comment           : POST /{object}/comments (message)
Insights          : GET /{post}/insights , GET /{media}/insights

All functions honour settings.DRY_RUN (log the call, return a fake id).
"""
from __future__ import annotations

import time

import requests

from engine import settings

BASE = f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}"


class MetaError(RuntimeError):
    pass


def configured() -> bool:
    return bool(settings.META_PAGE_ID and settings.META_PAGE_TOKEN)


def _call(method: str, path: str, **params) -> dict:
    params.setdefault("access_token", settings.META_PAGE_TOKEN)
    if settings.DRY_RUN:
        safe = {k: (v if k != "access_token" else "***") for k, v in params.items()}
        print(f"    [dry-run] {method} {path} {safe}")
        return {"id": f"dry_{int(time.time()*1000) % 10_000_000}"}
    url = f"{BASE}/{path.lstrip('/')}"
    for attempt in range(3):
        r = requests.request(method, url, params=params if method == "GET" else None,
                             data=params if method != "GET" else None, timeout=120)
        if r.status_code >= 500 or r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        try:
            data = r.json()
        except ValueError:
            raise MetaError(f"{r.status_code}: {r.text[:200]}")
        if "error" in data:
            err = data["error"]
            raise MetaError(f"{err.get('code')} {err.get('type')}: {err.get('message')}")
        return data
    raise MetaError(f"Graph API unavailable after retries: {r.status_code}")


# ── Facebook ───────────────────────────────────────────────────────────────
def _backdate(params: dict, backdated_time: int | None) -> dict:
    """Page posts may carry a past timestamp: they appear at that point in the timeline and
    followers are not notified — what a launch backfill wants."""
    if backdated_time:
        params["backdated_time"] = str(int(backdated_time))
        params["backdated_time_granularity"] = "hour"
    return params


def fb_upload_photo(url: str, published: bool = False, message: str = "", backdated_time: int | None = None) -> str:
    p = {"url": url, "published": "true" if published else "false"}
    if message:
        p["message"] = message
    if published:
        _backdate(p, backdated_time)
    return _call("POST", f"/{settings.META_PAGE_ID}/photos", **p)["id"]


def fb_publish(media_urls: list[str], message: str, backdated_time: int | None = None) -> str:
    """Single photo → photos endpoint; several → feed with attached_media."""
    if not media_urls:
        raise MetaError("no media")
    if len(media_urls) == 1:
        return fb_upload_photo(media_urls[0], published=True, message=message, backdated_time=backdated_time)
    ids = [fb_upload_photo(u) for u in media_urls]
    params = _backdate({"message": message}, backdated_time)
    for i, pid in enumerate(ids):
        params[f"attached_media[{i}]"] = f'{{"media_fbid":"{pid}"}}'
    return _call("POST", f"/{settings.META_PAGE_ID}/feed", **params)["id"]


def fb_story(url: str) -> str:
    pid = fb_upload_photo(url, published=False)
    return _call("POST", f"/{settings.META_PAGE_ID}/photo_stories", photo_id=pid).get("post_id", pid)


def fb_comment(object_id: str, message: str) -> str:
    return _call("POST", f"/{object_id}/comments", message=message)["id"]


# Meta keeps retiring post metrics (post_engaged_users; the June 2026 reach switch to media views), and one
# retired name fails the whole request with #100 — so each figure is asked for alone, newest name first.
_FB_METRICS = {
    "reach": ("post_total_media_view_unique", "post_impressions_unique"),
    "clicks": ("post_clicks",),
}


def _fb_metric(post_id: str, names: tuple[str, ...]):
    for name in names:
        try:
            data = _call("GET", f"/{post_id}/insights", metric=name).get("data") or []
        except MetaError:
            continue
        if data:
            vals = data[0].get("values") or [{}]
            return vals[-1].get("value")
    return None


def fb_post_insights(post_id: str) -> dict:
    out = {key: _fb_metric(post_id, names) or 0 for key, names in _FB_METRICS.items()}
    # reactions/shares/comments come from the post object itself, not the insights edge
    obj = _call("GET", f"/{post_id}",
                fields="shares,comments.summary(true).limit(0),reactions.summary(true).limit(0)")
    out["shares"] = (obj.get("shares") or {}).get("count", 0)
    out["comments"] = ((obj.get("comments") or {}).get("summary") or {}).get("total_count", 0)
    out["reactions"] = ((obj.get("reactions") or {}).get("summary") or {}).get("total_count", 0)
    return out


# ── Instagram ──────────────────────────────────────────────────────────────
def _ig_wait(container_id: str, timeout_s: int = 120) -> None:
    if settings.DRY_RUN:
        return
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = _call("GET", f"/{container_id}", fields="status_code,status")
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            raise MetaError(f"IG container error: {st}")
        time.sleep(4)
    raise MetaError("IG container not ready in time")


def ig_publish(media_urls: list[str], caption: str) -> str:
    ig = settings.META_IG_USER_ID
    if not ig:
        raise MetaError("META_IG_USER_ID not set")
    if len(media_urls) == 1:
        c = _call("POST", f"/{ig}/media", image_url=media_urls[0], caption=caption)["id"]
    else:
        children = []
        for u in media_urls[:10]:
            children.append(_call("POST", f"/{ig}/media", image_url=u, is_carousel_item="true")["id"])
        for cid in children:
            _ig_wait(cid)
        c = _call("POST", f"/{ig}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    _ig_wait(c)
    return _call("POST", f"/{ig}/media_publish", creation_id=c)["id"]


def ig_story(url: str) -> str:
    ig = settings.META_IG_USER_ID
    c = _call("POST", f"/{ig}/media", image_url=url, media_type="STORIES")["id"]
    _ig_wait(c)
    return _call("POST", f"/{ig}/media_publish", creation_id=c)["id"]


def ig_comment(media_id: str, message: str) -> str:
    return _call("POST", f"/{media_id}/comments", message=message)["id"]


def ig_media_insights(media_id: str) -> dict:
    data = _call("GET", f"/{media_id}/insights", metric="reach,saved,shares,likes,comments,total_interactions")
    return {m["name"]: (m.get("values") or [{}])[0].get("value") for m in data.get("data", [])}


# ── token health ───────────────────────────────────────────────────────────
def token_info() -> dict:
    data = _call("GET", "/debug_token", input_token=settings.META_PAGE_TOKEN)
    return data.get("data", {})


def page_name() -> str:
    return _call("GET", f"/{settings.META_PAGE_ID}", fields="name,link").get("name", "")
