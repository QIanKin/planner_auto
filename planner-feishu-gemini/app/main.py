from __future__ import annotations

import asyncio
import json
import os
from typing import Dict, List

from . import gemini
from .data_io import (
    append_delivery,
    load_latest_plan_md,
    load_users,
    read_agenda,
    write_agenda,
)
from .feishu import send_text
from .render import render_text
from .timewin import in_push_window, now_utc, to_local
from .types import Agenda

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
PROMPT_JSON_PATH = os.path.join(ROOT_DIR, "prompt.json.txt")
PROMPT_TEXT_PATH = os.path.join(ROOT_DIR, "prompt.text.txt")

PUSH_HOUR = int(os.getenv("PUSH_HOUR", "7"))
PUSH_WINDOW_MIN = int(os.getenv("PUSH_WINDOW_MIN", "7"))


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_code_fence(s: str) -> str:
    t = s.strip()
    if t.startswith("```"):
        # remove first fence line
        t = t.split("\n", 1)[1] if "\n" in t else ""
        # remove trailing fence
        if t.endswith("```"):
            t = t[: -3]
    # remove leading json hint
    if t.lower().startswith("json\n"):
        t = t[5:]
    return t.strip()


async def process_user(user: Dict, utc_now) -> None:
    public_id = user["public_id"]
    timezone = user["timezone"]
    webhook = user.get("feishu_webhook")
    user_secret = user.get("feishu_secret")
    prefs = user.get("prefs") or ""

    local_now = to_local(utc_now, timezone)
    if not in_push_window(local_now, hour=PUSH_HOUR, window_minutes=PUSH_WINDOW_MIN):
        return

    date_str = local_now.strftime("%Y-%m-%d")

    # If agenda exists, read and push
    existing = read_agenda(public_id, date_str)
    if existing:
        text = render_text(existing)
        ok, resp = await send_text(webhook, text, user_secret)
        append_delivery(public_id, date_str, "feishu", ok, resp)
        return

    # Else, generate from latest plan
    plan_md = load_latest_plan_md(public_id)
    if not plan_md:
        append_delivery(public_id, date_str, "feishu", False, "no_plan_md")
        return

    today_str = date_str
    # JSON-first
    try:
        json_tpl = _read_text(PROMPT_JSON_PATH)
        json_prompt = json_tpl.format(today=today_str, prefs=prefs, content=plan_md)
        raw = await gemini.generate_text(json_prompt)
        raw = _strip_code_fence(raw)
        obj = json.loads(raw)
        agenda = Agenda(**obj).model_dump()
        write_agenda(public_id, date_str, agenda)
        text = render_text(agenda)
        ok, resp = await send_text(webhook, text, user_secret)
        append_delivery(public_id, date_str, "feishu", ok, resp)
        return
    except Exception as exc:
        # Fallback to text mode
        pass

    try:
        txt_tpl = _read_text(PROMPT_TEXT_PATH)
        txt_prompt = txt_tpl.format(today=today_str, prefs=prefs, content=plan_md)
        text = await gemini.generate_text(txt_prompt)
        ok, resp = await send_text(webhook, text, user_secret)
        append_delivery(public_id, date_str, "feishu", ok, resp)
    except Exception as exc:
        append_delivery(public_id, date_str, "feishu", False, f"fallback_error: {exc}")


async def main() -> None:
    utc_now = now_utc()
    users = load_users()
    tasks: List[asyncio.Task] = []
    for u in users:
        tasks.append(asyncio.create_task(process_user(u, utc_now)))
    if tasks:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
