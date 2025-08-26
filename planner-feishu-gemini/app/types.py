from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Block(BaseModel):
    start: str
    end: str
    task: str
    checklist: Optional[List[str]] = None
    priority: str = Field(default="S")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"M", "S", "C"}
        if v not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return v


class Agenda(BaseModel):
    date: str
    focus: str
    blocks: List[Block]
    reminders: Optional[List[str]] = None
    risks: Optional[List[str]] = None
