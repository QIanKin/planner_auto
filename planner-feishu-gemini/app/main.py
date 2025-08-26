from __future__ import annotations

import asyncio
import json
import os
from typing import Dict, List

from . import gemini
from .data_io import (
    append_delivery,
    load_preferred_plan_md,
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
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.endswith("```"):
            t = t[: -3]
    if t.lower().startswith("json\n"):
        t = t[5:]
    return t.strip()


def _extract_json_object(s: str) -> str:
    t = s.strip()
    if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
        t = t[1:-1].strip()
    start = t.find('{')
    if start == -1:
        # Attempt recovery: wrap key-value lines as an object
        return '{' + t + '}'
    depth = 0
    for idx in range(start, len(t)):
        ch = t[idx]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return t[start:idx+1]
    return t[start:]


def _sanitize_json_like(s: str) -> str:
    t = s
    # remove trailing commas before } or ]
    t = t.replace(',\n}', '\n}')
    t = t.replace(',\n ]', '\n ]')
    t = t.replace(', }', ' }')
    t = t.replace(', ]', ' ]')
    return t


def _save_debug(public_id: str, date_str: str, *, raw: str | None, cleaned: str | None, candidate: str | None, err: Exception | None) -> None:
    return None


def _pad_time_component(comp: str) -> str:
    comp = comp.strip()
    return comp.zfill(2)


def _norm_time(hhmm: str) -> str:
    # Accept formats like 9:30 or 09:30, return HH:MM
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        return hhmm.strip()
    return f"{_pad_time_component(parts[0])}:{_pad_time_component(parts[1])}"


def _normalize_schema(obj: dict, today_str: str) -> dict:
    # If already appears to be our schema, return as-is
    if isinstance(obj, dict) and "date" in obj and "blocks" in obj:
        return obj

    # Handle Chinese schema: {"今日行程": { "重点": [...], "上午": [...], "下午": [...], "晚上": {...}|[...] , "温馨提醒": "..." }}
    root = obj
    if "今日行程" in obj and isinstance(obj["今日行程"], dict):
        root = obj["今日行程"]

    focus = ""
    blocks = []
    reminders = []

    # 重点 -> focus (join)
    if isinstance(root.get("重点"), list):
        focus = "；".join([str(x) for x in root.get("重点") if x is not None])[:200]

    def collect_period(period_value):
        if isinstance(period_value, list):
            return period_value
        if isinstance(period_value, dict):
            return [period_value]
        return []

    for period_key in ["上午", "下午", "晚上"]:
        for item in collect_period(root.get(period_key)):
            if not isinstance(item, dict):
                continue
            time_str = str(item.get("时间", "")).strip()
            task = str(item.get("活动", "")).strip()
            # Parse time range e.g., 9:30-11:30
            if "-" in time_str:
                start_s, end_s = [x.strip() for x in time_str.split("-", 1)]
                start_s, end_s = _norm_time(start_s), _norm_time(end_s)
            else:
                # Fallback: unknown range, skip
                continue
            blocks.append({
                "start": start_s,
                "end": end_s,
                "task": task,
                "priority": "S",
            })

    # 温馨提醒 -> reminders
    if root.get("温馨提醒"):
        reminders = [str(root.get("温馨提醒"))]

    normalized = {
        "date": today_str,
        "focus": focus,
        "blocks": blocks,
        "reminders": reminders,
        "risks": [],
    }
    return normalized


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

    existing = read_agenda(public_id, date_str)
    if existing:
        text = render_text(existing)
        ok, resp = await send_text(webhook, text, user_secret)
        append_delivery(public_id, date_str, "feishu", ok, resp)
        return

    plan_md = load_preferred_plan_md(public_id, date_str)
    if not plan_md:
        append_delivery(public_id, date_str, "feishu", False, "no_plan_md")
        return

    today_str = date_str
    try:
        json_tpl = _read_text(PROMPT_JSON_PATH)
        json_prompt = json_tpl.format(today=today_str, prefs=prefs, content=plan_md)
        raw = await gemini.generate_text(json_prompt)
        cleaned = _strip_code_fence(raw)
        candidate = _extract_json_object(cleaned)
        sanitized = _sanitize_json_like(candidate)
        try:
            obj = json.loads(sanitized)
        except Exception as exc_inner:
            # If JSON.loads fails, try to coerce quotes
            sanitized2 = sanitized.replace("'", '"')
            obj = json.loads(sanitized2)
        try:
            agenda = Agenda(**obj).model_dump()
        except Exception:
            # Normalize alternative schema into our schema
            normalized = _normalize_schema(obj, today_str)
            agenda = Agenda(**normalized).model_dump()
        write_agenda(public_id, date_str, agenda)
        text = render_text(agenda)
        ok, resp = await send_text(webhook, text, user_secret)
        append_delivery(public_id, date_str, "feishu", ok, resp)
        return
    except Exception as exc:
        try:
            _save_debug(public_id, date_str, raw=locals().get('raw'), cleaned=locals().get('cleaned'), candidate=locals().get('sanitized') or locals().get('candidate'), err=exc)
        except Exception:
            pass

    try:
        txt_tpl = _read_text(PROMPT_TEXT_PATH)
        txt_prompt = txt_tpl.format(today=today_str, prefs=prefs, content=plan_md)
        text = await gemini.generate_text(txt_prompt)
        # If fallback looks like JSON, parse -> normalize -> render -> send
        sent = False
        if text and '{' in text and '}' in text:
            try:
                cleaned_fb = _strip_code_fence(text)
                candidate_fb = _extract_json_object(cleaned_fb)
                sanitized_fb = _sanitize_json_like(candidate_fb)
                obj_fb = json.loads(sanitized_fb)
                try:
                    agenda_fb = Agenda(**obj_fb).model_dump()
                except Exception:
                    agenda_fb = Agenda(**_normalize_schema(obj_fb, today_str)).model_dump()
                write_agenda(public_id, date_str, agenda_fb)
                rendered = render_text(agenda_fb)
                ok, resp = await send_text(webhook, rendered, user_secret)
                append_delivery(public_id, date_str, "feishu", ok, resp)
                sent = True
            except Exception:
                sent = False
        if not sent:
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
