from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional, Tuple

import httpx


def gen_signature(secret: str) -> tuple[str, str]:
    """Generate Feishu bot signature tuple (timestamp, sign).

    Algorithm: sign = Base64( HMAC-SHA256( key=secret, msg=f"{timestamp}\n{secret}" ) )
    """
    if not secret:
        raise ValueError("secret must be non-empty to generate signature")
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = base64.b64encode(digest).decode("utf-8")
    return timestamp, sign


async def send_text(webhook: str, text: str, secret: Optional[str] = None) -> tuple[bool, str]:
    """Send text message to Feishu custom bot webhook.

    If secret is provided, append &timestamp=...&sign=... query params.

    Returns (ok, response_text). Non-200 or Feishu StatusCode != 0 => ok=False.
    """
    if not webhook:
        return False, "missing webhook"

    url = webhook
    if secret:
        try:
            ts, sign = gen_signature(secret)
            delimiter = '&' if ('?' in url) else '?'
            url = f"{url}{delimiter}timestamp={ts}&sign={sign}"
        except Exception as exc:
            return False, f"signature_error: {exc}"

    payload = {"msg_type": "text", "content": {"text": text}}
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, headers=headers, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            return False, f"http_error: {exc}"

    if resp.status_code != 200:
        return False, f"http_status_{resp.status_code}: {resp.text}"

    try:
        data = resp.json()
    except Exception:
        return False, f"invalid_json_response: {resp.text[:500]}"

    status = data.get("StatusCode")
    if status not in (0, None):
        return False, json.dumps(data, ensure_ascii=False)

    return True, json.dumps(data, ensure_ascii=False)
