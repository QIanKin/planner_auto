from __future__ import annotations

from typing import Dict, List


def _format_block(block: Dict) -> str:
    start = block.get("start", "??:??")
    end = block.get("end", "??:??")
    task = block.get("task", "")
    priority = block.get("priority", "S")
    lines = [f"• {start}-{end}  {task}  [{priority}]"]
    checklist = block.get("checklist") or []
    for item in checklist:
        lines.append(f"   - [ ] {item}")
    return "\n".join(lines)


def render_text(agenda: Dict) -> str:
    date = agenda.get("date", "")
    focus = agenda.get("focus", "")
    blocks: List[Dict] = agenda.get("blocks", [])
    reminders: List[str] = agenda.get("reminders") or []
    risks: List[str] = agenda.get("risks") or []

    parts: List[str] = []
    parts.append(f"📅 {date}｜主题：{focus}")
    parts.append("")
    for b in blocks:
        parts.append(_format_block(b))
    if reminders:
        parts.append("")
        parts.append("⏰ 提醒：")
        for r in reminders:
            parts.append(f"- {r}")
    if risks:
        parts.append("")
        parts.append("⚠️ 风险：")
        for r in risks:
            parts.append(f"- {r}")

    return "\n".join(parts).strip()
