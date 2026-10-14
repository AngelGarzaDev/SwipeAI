"""Local vision-LLM judgement step for profile vetting.

Talks to any OpenAI-compatible chat endpoint (Ollama, llama.cpp server,
LM Studio, vLLM...). Standard library only.

Config is the [llm] section of config.toml (config.py applies env overrides).
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request

import cv2

DEFAULT_PROMPT = """You are vetting a dating profile for the user.
Look at the main profile photo and read the profile text, then decide LIKE or DISLIKE.

User preferences:
{preferences}

Profile text (OCR, may contain small errors):
Name: {name}
Age: {age}
Text: {bio}

Reply with ONLY a JSON object, no other text:
{{"decision": "LIKE" or "DISLIKE", "reason": "<one short sentence>"}}"""


def enabled(c):
    """c = the [llm] config section."""
    return bool(c.get("enabled") and c.get("url") and c.get("model"))


def _encode(img, max_side):
    s = min(1.0, max_side / max(img.shape[:2]))
    if s < 1.0:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode()


def _parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            dec = str(d.get("decision", "")).upper()
            if dec in ("LIKE", "DISLIKE"):
                return dec, str(d.get("reason", ""))
        except json.JSONDecodeError:
            pass
    # Lenient fallback: first decision keyword in the text.
    m = re.search(r"\b(DISLIKE|LIKE)\b", text.upper())
    if m:
        return m.group(1), text.strip()[:200]
    raise ValueError(f"unparseable LLM reply: {text[:200]!r}")


def judge(photo, report, c):
    """c = the [llm] config section. Returns dict(decision, reason, raw, seconds, attempts).
    Raises once every attempt has failed."""
    prompt = c.get("prompt") or DEFAULT_PROMPT
    prompt = prompt.format(preferences=c.get("preferences", "(none given)"),
                           name=report.get("name"), age=report.get("age"),
                           bio=report.get("bio") or "")
    body = {
        "model": c["model"],
        "temperature": c.get("temperature", 0.1),
        "max_tokens": c.get("max_tokens", 200),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + _encode(photo, c.get("image_max_side", 768))}},
        ]}],
    }
    url = c["url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {c.get('api_key') or 'none'}"})

    # Retry timeouts, connection errors, server errors and unparseable replies, waiting
    # retry_delay, 2x retry_delay, ... between attempts. Client errors (bad URL/model/key)
    # won't fix themselves, so they fail at once.
    attempts = 1 + max(0, int(c.get("retries", 2)))
    delay = float(c.get("retry_delay", 5))
    for attempt in range(1, attempts + 1):
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=c.get("timeout", 120)) as r:
                resp = json.load(r)
            raw = resp["choices"][0]["message"]["content"]
            decision, reason = _parse(raw)
            return {"decision": decision, "reason": reason, "raw": raw, "model": c["model"],
                    "seconds": round(time.time() - t, 2), "attempts": attempt}
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code not in (408, 429) or attempt == attempts:
                raise
            err = e
        except Exception as e:  # noqa: BLE001 - timeouts, refused connections, bad replies
            if attempt == attempts:
                raise RuntimeError(f"{e} (after {attempts} attempts)") from e
            err = e
        wait = delay * 2 ** (attempt - 1)
        print(f"DEBUG: LLM attempt {attempt}/{attempts} failed ({err}); retrying in {wait:g}s")
        time.sleep(wait)
