"""Warm-up stage + daily-cap math. Pure functions — easy to unit test."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.enums import WarmupStage

# Stage -> daily cap. `full` means provider/pool ceiling (sentinel large number).
STAGE_CAPS: dict[WarmupStage, int] = {
    WarmupStage.stage_1: 5,
    WarmupStage.stage_2: 10,
    WarmupStage.stage_3: 20,
    WarmupStage.full: 1000,
}


def stage_for_age(started_at: datetime | None, now: datetime | None = None) -> WarmupStage:
    """Map warm-up age to a stage: d1-3=5, d4-7=10, d8-14=20, d15+=full."""
    if started_at is None:
        return WarmupStage.stage_1
    now = now or datetime.now(timezone.utc)
    age_days = (now - started_at).days
    if age_days < 3:
        return WarmupStage.stage_1
    if age_days < 7:
        return WarmupStage.stage_2
    if age_days < 14:
        return WarmupStage.stage_3
    return WarmupStage.full


def daily_cap(stage: WarmupStage) -> int:
    return STAGE_CAPS[stage]


def is_new_day(count_date: date | None, today: date | None = None) -> bool:
    today = today or datetime.now(timezone.utc).date()
    return count_date != today
