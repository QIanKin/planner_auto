from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from glob import glob
from typing import Dict, List, Optional

import pytz

DATA_DIR = "data"
PLANS_DIR = os.path.join(DATA_DIR, "plans")
AGENDAS_DIR = os.path.join(DATA_DIR, "agendas")
DELIVERIES_CSV = os.path.join(DATA_DIR, "deliveries.csv")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _strip(s: Optional[str]) -> str:
    return (s or "").strip()


def load_users() -> List[Dict]:
    users_path = os.path.join(DATA_DIR, "users.csv")
    if not os.path.exists(users_path):
        return []
    users: List[Dict] = []
    with open(users_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            public_id = _strip(row.get("public_id"))
            if not public_id:
                continue
            active_raw = _strip(row.get("active")).lower()
            active = active_raw == "true"
            if not active:
                continue
            users.append(
                {
                    "public_id": public_id,
                    "timezone": _strip(row.get("timezone")) or "Asia/Shanghai",
                    "feishu_webhook": _strip(row.get("feishu_webhook")),
                    "feishu_secret": _strip(row.get("feishu_secret")) or None,
                    "prefs": _strip(row.get("prefs")),
                }
            )
    return users


def load_latest_plan_md(public_id: str) -> Optional[str]:
    pattern = os.path.join(PLANS_DIR, f"{public_id}.*.md")
    files = glob(pattern)
    if not files:
        return None
    # pick latest modified
    latest = max(files, key=lambda p: os.path.getmtime(p))
    try:
        with open(latest, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def load_preferred_plan_md(public_id: str, date_str: str) -> Optional[str]:
    """Prefer a plan file for the given date: {public_id}.{YYYY-MM-DD}*.md; else fallback to latest.
    """
    pattern_today = os.path.join(PLANS_DIR, f"{public_id}.{date_str}*.md")
    files_today = glob(pattern_today)
    if files_today:
        latest_today = max(files_today, key=lambda p: os.path.getmtime(p))
        try:
            with open(latest_today, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return load_latest_plan_md(public_id)


def _agenda_path(public_id: str, date_str: str) -> str:
    date_dir = os.path.join(AGENDAS_DIR, date_str)
    _ensure_dir(date_dir)
    return os.path.join(date_dir, f"{public_id}.json")


def read_agenda(public_id: str, date_str: str) -> Optional[Dict]:
    path = _agenda_path(public_id, date_str)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_agenda(public_id: str, date_str: str, agenda: Dict) -> None:
    path = _agenda_path(public_id, date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(agenda, f, ensure_ascii=False, indent=2)


def append_delivery(public_id: str, date_str: str, channel: str, ok: bool, provider_msg: str) -> None:
    header = ["ts", "public_id", "date", "channel", "status", "provider_message"]
    need_header = not os.path.exists(DELIVERIES_CSV)
    with open(DELIVERIES_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if need_header:
            writer.writerow(header)
        ts = datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()
        writer.writerow([ts, public_id, date_str, channel, "ok" if ok else "fail", provider_msg])
