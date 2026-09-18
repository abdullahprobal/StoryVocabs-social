"""Public URLs for rendered PNGs (Instagram's API only accepts URLs).

github   : commits files to a PUBLIC repo via the Contents API; served from raw.githubusercontent.com
supabase : uploads to a public Storage bucket (needs SUPABASE_URL + SUPABASE_SERVICE_ROLE)
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from engine import settings


def configured() -> bool:
    if settings.MEDIA_HOST == "supabase":
        return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE)
    return bool(settings.MEDIA_REPO and settings.MEDIA_REPO_TOKEN)


def _github_put(rel_path: str, data: bytes) -> str:
    api = f"https://api.github.com/repos/{settings.MEDIA_REPO}/contents/{rel_path}"
    headers = {"Authorization": f"Bearer {settings.MEDIA_REPO_TOKEN}", "Accept": "application/vnd.github+json"}
    body = {"message": f"media: {rel_path}", "content": base64.b64encode(data).decode(), "branch": settings.MEDIA_REPO_BRANCH}
    # If the file exists we must pass its sha to overwrite it.
    r = requests.get(api, headers=headers, params={"ref": settings.MEDIA_REPO_BRANCH}, timeout=60)
    if r.status_code == 200:
        body["sha"] = r.json()["sha"]
    r = requests.put(api, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return f"https://raw.githubusercontent.com/{settings.MEDIA_REPO}/{settings.MEDIA_REPO_BRANCH}/{rel_path}"


def _supabase_put(rel_path: str, data: bytes) -> str:
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_path}"
    headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE}", "apikey": settings.SUPABASE_SERVICE_ROLE,
               "Content-Type": "image/png", "x-upsert": "true"}
    r = requests.post(url, headers=headers, data=data, timeout=120)
    r.raise_for_status()
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{rel_path}"


def upload_many(paths: list[str], prefix: str) -> list[str]:
    urls = []
    for p in paths:
        pth = Path(p)
        rel = f"{prefix}/{pth.name}"
        data = pth.read_bytes()
        urls.append(_supabase_put(rel, data) if settings.MEDIA_HOST == "supabase" else _github_put(rel, data))
    return urls
