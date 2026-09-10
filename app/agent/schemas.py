"""Pydantic shapes for LLM output. Untrusted JSON is forced into these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ItemType = Literal[
    "earnings",
    "8-k",
    "form-4",
    "10-q",
    "10-k",
    "product",
    "news",
    "other",
]


"Agent 1 - Summarize"


class ItemSummaryOut(BaseModel):
    item_type: ItemType
    summary: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    key_numbers: list[str] = Field(default_factory=list)


"Agent 2 - Rank"


class RankedPick(BaseModel):
    summary_id: str
    reason: str = Field(min_length=1)


class RankOut(BaseModel):
    picks: list[RankedPick] = Field(min_length=1, max_length=10)
    rationale: str = Field(min_length=1)


"Agent 3 - Email"


class EmailOut(BaseModel):
    subject: str = Field(min_length=1)
    overview: list[str] = Field(min_length=1, max_length=3)

    @field_validator("overview")
    @classmethod
    def overview_paragraphs(cls, value: list[str]) -> list[str]:
        cleaned = [paragraph.strip() for paragraph in value if paragraph.strip()]
        if not cleaned:
            raise ValueError("overview must contain at least one paragraph")
        return cleaned
