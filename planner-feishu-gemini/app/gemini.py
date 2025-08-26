from __future__ import annotations

import json
import os
from typing import Optional

import httpx

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


class GeminiError(RuntimeError):
    pass


async def generate_text(prompt: str, model: Optional[str] = None) -> str:
    """Call Google Generative Language API v1beta generateContent and return text.

    Args:
        prompt: The prompt string.
        model: Optional model name; defaults to env GEMINI_MODEL or gemini-1.5-flash.

    Returns:
        The text from candidates[0].content.parts[0].text.

    Raises:
        GeminiError on HTTP or payload errors.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("Missing GOOGLE_API_KEY env")
    mdl = model or DEFAULT_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000},
    }

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, headers=headers, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            raise GeminiError(f"http_error: {exc}") from exc

    if resp.status_code != 200:
        raise GeminiError(f"status_{resp.status_code}: {resp.text}")

    try:
        data = resp.json()
    except Exception as exc:
        raise GeminiError(f"invalid_json_response: {resp.text[:500]}") from exc

    try:
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
    except Exception as exc:
        raise GeminiError(f"unexpected_payload: {json.dumps(data, ensure_ascii=False)[:500]}") from exc

    if not text:
        raise GeminiError(f"empty_text: {json.dumps(data, ensure_ascii=False)[:500]}")

    return text.strip()
