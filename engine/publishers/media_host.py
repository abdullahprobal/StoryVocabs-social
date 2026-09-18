"""Public URLs for rendered PNGs (Instagram's API only accepts URLs).

github   : pushes files to a PUBLIC repo; served from raw.githubusercontent.com
           - with MEDIA_DEPLOY_KEY (SSH private key) → git push (no personal token needed)
           - or with MEDIA_REPO_TOKEN (fine-grained PAT) → Contents API
supabase : uploads to a public Storage bucket (SUPABASE_URL + SUPABASE_SERVICE_ROLE)
"""
from __future__ import annotations

import base64
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import requests

from engine import settings

MEDIA_DEPLOY_KEY = os.getenv("MEDIA_DEPLOY_KEY", "")


def configured() -> bool:
    if settings.MEDIA_HOST == "supabase":
        return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE)
    return bool(settings.MEDIA_REPO and (MEDIA_DEPLOY_KEY or settings.MEDIA_REPO_TOKEN))


def raw_url(rel_path: str) -> str:
    return f"https://raw.githubusercontent.com/{settings.MEDIA_REPO}/{settings.MEDIA_REPO_BRANCH}/{rel_path}"


# ── github via deploy key (git push) ───────────────────────────────────────
def _git_push_files(files: list[tuple[str, Path]]) -> list[str]:
    """files: [(rel_path, local_path)] → raw URLs. One clone, one commit, one push."""
    work = Path(tempfile.mkdtemp(prefix="svmedia_"))
    key_file = work / "deploy_key"
    key_file.write_text(MEDIA_DEPLOY_KEY.replace("\r\n", "\n").rstrip() + "\n", encoding="utf-8")
    key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
    env = {**os.environ,
           "GIT_SSH_COMMAND": f'ssh -i "{key_file}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new',
           "GIT_TERMINAL_PROMPT": "0"}
    repo = work / "repo"
    url = f"git@github.com:{settings.MEDIA_REPO}.git"
    try:
        subprocess.run(["git", "clone", "--depth", "1", "--branch", settings.MEDIA_REPO_BRANCH, url, str(repo)],
                       check=True, env=env, capture_output=True, text=True)
        for rel, local in files:
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, dest)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=storyvocabs-bot", "-c", "user.email=bot@storyvocabs.local",
                        "commit", "-q", "-m", f"media: {files[0][0].rsplit('/', 1)[0] if files else 'upload'}"],
                       check=True, env=env, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", settings.MEDIA_REPO_BRANCH],
                       check=True, env=env, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"media git push failed: {e.stderr or e.stdout}") from e
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return [raw_url(rel) for rel, _ in files]


# ── github via Contents API (PAT) ──────────────────────────────────────────
def _github_put(rel_path: str, data: bytes) -> str:
    api = f"https://api.github.com/repos/{settings.MEDIA_REPO}/contents/{rel_path}"
    headers = {"Authorization": f"Bearer {settings.MEDIA_REPO_TOKEN}", "Accept": "application/vnd.github+json"}
    body = {"message": f"media: {rel_path}", "content": base64.b64encode(data).decode(), "branch": settings.MEDIA_REPO_BRANCH}
    r = requests.get(api, headers=headers, params={"ref": settings.MEDIA_REPO_BRANCH}, timeout=60)
    if r.status_code == 200:
        body["sha"] = r.json()["sha"]
    r = requests.put(api, headers=headers, json=body, timeout=120)
    r.raise_for_status()
    return raw_url(rel_path)


# ── supabase storage ───────────────────────────────────────────────────────
def _supabase_put(rel_path: str, data: bytes) -> str:
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}/{rel_path}"
    headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE}", "apikey": settings.SUPABASE_SERVICE_ROLE,
               "Content-Type": "image/png", "x-upsert": "true"}
    r = requests.post(url, headers=headers, data=data, timeout=120)
    r.raise_for_status()
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{rel_path}"


def upload_many(paths: list[str], prefix: str) -> list[str]:
    pairs = [(f"{prefix}/{Path(p).name}", Path(p)) for p in paths]
    if settings.MEDIA_HOST == "supabase":
        return [_supabase_put(rel, local.read_bytes()) for rel, local in pairs]
    if MEDIA_DEPLOY_KEY:
        return _git_push_files(pairs)
    return [_github_put(rel, local.read_bytes()) for rel, local in pairs]
