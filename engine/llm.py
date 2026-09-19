"""Free-tier LLM chain with structured (JSON) output.

    from engine.llm import call_json
    post = call_json(system, user, StoryPost)   # returns a validated StoryPost

Providers (all free tiers, all via plain HTTPS so there is one dependency):
  gemini     generativelanguage.googleapis.com  (native JSON mode)
  groq       api.groq.com/openai/v1             (json_object mode, key rotation)
  cerebras   api.cerebras.ai/v1                 (OpenAI-compatible)
  openrouter openrouter.ai/api/v1               (OpenAI-compatible, :free models)

Behaviour:
  * walks settings.llm_chain() in order; skips providers without a key
  * 429 / 5xx / timeouts put that (provider, model) on cool-down for the run
  * output is parsed leniently (code fences stripped), then validated with the
    pydantic model; a validation error triggers ONE repair call on the same
    provider with the error text, then the next provider
  * every call is logged to state/llm_log.jsonl (provider, model, ms, ok)
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from engine import settings

T = TypeVar("T", bound=BaseModel)

_COOLDOWN: dict[tuple[str, str], float] = {}
_GROQ_KEY_IDX = 0
LOG_FILE = settings.STATE_DIR / "llm_log.jsonl"


class LLMError(RuntimeError):
    pass


# ── helpers ────────────────────────────────────────────────────────────────
def extract_json(raw: str) -> str:
    """Pull the first JSON object out of a model reply (handles ``` fences)."""
    if not raw:
        raise ValueError("empty reply")
    s = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if fence:
        s = fence.group(1).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    return s[start : end + 1]


_KEY_IN_URL = re.compile(r"([?&](?:key|api_key|token)=)[^&\s\"']+", re.I)


def _log(provider, model, ms, ok, note=""):
    note = _KEY_IN_URL.sub(r"\1<redacted>", note or "")  # provider errors echo the request URL
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "provider": provider, "model": model, "ms": int(ms), "ok": ok, "note": note[:200],
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _schema_hint(model_cls: Type[BaseModel]) -> str:
    schema = model_cls.model_json_schema()
    return json.dumps(schema, ensure_ascii=False)


# ── raw provider calls: each returns the reply text or raises ──────────────
def _openai_compatible(base_url, api_key, model, system, user, temperature, max_tokens, extra_headers=None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model:
        body["reasoning_effort"] = "low"
    r = requests.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=120)
    if r.status_code == 400 and ("response_format" in r.text or "json_validate_failed" in r.text):
        body.pop("response_format", None)
        r = requests.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=120)
    if r.status_code in (429, 500, 502, 503, 504):
        raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}", response=r)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


_GEMINI_KEY_IDX = 0
_BAD_GEMINI_KEYS: set[str] = set()


def _gemini(model, system, user, temperature, max_tokens):
    """Round-robin over GEMINI_API_KEY* ; a 429 (daily quota) or 4xx retires that key for the run."""
    global _GEMINI_KEY_IDX
    keys = [k for k in settings.GEMINI_API_KEYS if k not in _BAD_GEMINI_KEYS]
    if not keys:
        raise LLMError("gemini: no usable key")
    last = None
    for _ in range(len(keys)):
        key = keys[_GEMINI_KEY_IDX % len(keys)]
        _GEMINI_KEY_IDX += 1
        try:
            return _gemini_once(model, key, system, user, temperature, max_tokens)
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", 0)
            if status in (400, 401, 403, 429):
                _BAD_GEMINI_KEYS.add(key)
            last = e
    raise LLMError(f"gemini: all keys failed: {last}")


def _gemini_once(model, key, system, user, temperature, max_tokens):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
           f"?key={key}")
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    r = requests.post(url, json=body, timeout=120)
    if r.status_code in (429, 500, 502, 503, 504):
        raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}", response=r)
    r.raise_for_status()
    data = r.json()
    cands = data.get("candidates") or []
    if not cands:
        raise ValueError(f"gemini returned no candidates: {json.dumps(data)[:200]}")
    parts = cands[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


_BAD_GROQ_KEYS: set[str] = set()


def _groq(model, system, user, temperature, max_tokens):
    """Round-robin over GROQ_API_KEY_* ; a 401 retires that key for the run."""
    global _GROQ_KEY_IDX
    keys = [k for k in settings.GROQ_API_KEYS if k not in _BAD_GROQ_KEYS]
    if not keys:
        raise LLMError("no working groq key")
    last = None
    for round_ in range(2):  # a per-minute limit clears in seconds: one short wait, then a second pass
        for _ in range(len(keys)):
            key = keys[_GROQ_KEY_IDX % len(keys)]
            _GROQ_KEY_IDX += 1
            if key in _BAD_GROQ_KEYS:
                continue
            try:
                return _openai_compatible("https://api.groq.com/openai/v1", key, model, system, user, temperature, max_tokens)
            except requests.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                if status == 401:
                    _BAD_GROQ_KEYS.add(key)
                    last = e
                    continue
                if status == 429:
                    last = e
                    continue  # this key is rate-limited, try the next one
                raise
        if round_ == 0 and last is not None and "per minute" in str(last):
            time.sleep(25)
    raise LLMError(f"groq: all keys failed: {last}")


def _cerebras(model, system, user, temperature, max_tokens):
    return _openai_compatible("https://api.cerebras.ai/v1", settings.CEREBRAS_API_KEY, model,
                              system, user, temperature, max_tokens)


def _openrouter(model, system, user, temperature, max_tokens):
    return _openai_compatible("https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY, model,
                              system, user, temperature, max_tokens,
                              extra_headers={"HTTP-Referer": settings.PUBLIC_SITE_URL,
                                             "X-Title": f"{settings.BRAND_NAME} Social"})


_PROVIDERS = {"gemini": _gemini, "groq": _groq, "cerebras": _cerebras, "openrouter": _openrouter}


def _has_key(provider: str) -> bool:
    return {
        "gemini": bool(settings.GEMINI_API_KEYS),
        "groq": bool(settings.GROQ_API_KEYS),
        "cerebras": bool(settings.CEREBRAS_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
    }.get(provider, False)


def available_chain(avoid: str | None = None, strong: bool = False) -> list[tuple[str, str]]:
    """Healthy providers in order. `avoid` ("provider:model") is moved to the end so a critic
    can be a second opinion from a different model than the writer; `strong` drops the small
    models entirely (a weak critic is worse than the writer re-reading its own work)."""
    now = time.time()
    chain = [(p, m) for p, m in settings.llm_chain() if _has_key(p) and _COOLDOWN.get((p, m), 0) < now]
    if strong:
        chain = [c for c in chain if c[1] not in settings.WEAK_MODELS] or chain
    if avoid and len(chain) > 1:
        chain = [c for c in chain if f"{c[0]}:{c[1]}" != avoid] + [c for c in chain if f"{c[0]}:{c[1]}" == avoid]
    return chain


last_provider: str = ""  # "provider:model" that answered the most recent successful call


# ── public API ─────────────────────────────────────────────────────────────
def call_text(system: str, user: str, temperature: float = 0.7, max_tokens: int = 3000) -> str:
    """Plain text reply from the first healthy provider."""
    last = None
    for provider, model in available_chain():
        t0 = time.time()
        try:
            out = _PROVIDERS[provider](model, system, user, temperature, max_tokens)
            _log(provider, model, (time.time() - t0) * 1000, True)
            return out
        except (requests.RequestException, ValueError, LLMError) as e:
            _log(provider, model, (time.time() - t0) * 1000, False, str(e))
            _COOLDOWN[(provider, model)] = time.time() + 600
            last = e
    raise LLMError(f"all providers failed: {last}")


def call_json(system: str, user: str, model_cls: Type[T], temperature: float = 0.7,
              max_tokens: int = 3000, repair: bool = True, avoid: str | None = None, strong: bool = False) -> T:
    """Structured call: returns a validated instance of model_cls. Sets `last_provider`."""
    global last_provider
    schema_note = ("\n\nReturn ONLY a JSON object (no prose, no markdown) matching this JSON schema:\n"
                   + _schema_hint(model_cls))
    last: Exception | None = None
    for provider, model in available_chain(avoid, strong):
        t0 = time.time()
        try:
            raw = _PROVIDERS[provider](model, system + schema_note, user, temperature, max_tokens)
            try:
                obj = model_cls.model_validate_json(extract_json(raw))
                _log(provider, model, (time.time() - t0) * 1000, True)
                last_provider = f"{provider}:{model}"
                return obj
            except (ValidationError, ValueError, json.JSONDecodeError) as ve:
                if not repair:
                    raise
                fix_user = (f"{user}\n\nYour previous JSON was rejected with these errors:\n{str(ve)[:1200]}\n"
                            f"Previous JSON:\n{raw[:3000]}\n\nReturn the corrected JSON object only.")
                raw2 = _PROVIDERS[provider](model, system + schema_note, fix_user, min(temperature, 0.4), max_tokens)
                obj = model_cls.model_validate_json(extract_json(raw2))
                _log(provider, model, (time.time() - t0) * 1000, True, "repaired")
                last_provider = f"{provider}:{model}"
                return obj
        except (requests.RequestException, LLMError) as e:
            _log(provider, model, (time.time() - t0) * 1000, False, str(e))
            _COOLDOWN[(provider, model)] = time.time() + 600
            last = e
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            _log(provider, model, (time.time() - t0) * 1000, False, f"invalid: {str(e)[:120]}")
            last = e  # try the next provider, no cooldown
    raise LLMError(f"all providers failed for {model_cls.__name__}: {last}")
