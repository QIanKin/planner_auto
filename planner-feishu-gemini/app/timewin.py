from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pytz


def now_utc() -> datetime:
    """Return current UTC datetime with tzinfo set to UTC."""
    return datetime.utcnow().replace(tzinfo=pytz.utc)


def to_local(utc_dt: datetime, tz_name: str) -> datetime:
    """Convert a UTC datetime to a local timezone-aware datetime.

    Args:
        utc_dt: A timezone-aware UTC datetime (tzinfo=pytz.utc).
        tz_name: IANA timezone name, e.g., "Asia/Shanghai".

    Returns:
        Localized datetime in the target timezone.
    """
    if utc_dt.tzinfo is None:
        raise ValueError("utc_dt must be timezone-aware UTC datetime")
    if utc_dt.tzinfo != pytz.utc:
        # Normalize to UTC first if not exactly UTC tzinfo
        utc_dt = utc_dt.astimezone(pytz.utc)
    try:
        tz = pytz.timezone(tz_name)
    except Exception as exc:
        raise ValueError(f"Invalid timezone name: {tz_name}") from exc
    return utc_dt.astimezone(tz)


def in_push_window(local_dt: datetime, hour: int = 7, window_minutes: int = 7) -> bool:
    """Determine if local time is within [hour:00 ± window_minutes].

    The window is inclusive, centered on hour:00. For example, at hour=7 and window=7,
    the window is from 06:53:00 to 07:07:59.999...

    Args:
        local_dt: Local timezone-aware datetime.
        hour: Target hour (0-23), default 7.
        window_minutes: Symmetric window size in minutes, default 7.

    Returns:
        True if within the window; False otherwise.
    """
    if local_dt.tzinfo is None:
        raise ValueError("local_dt must be timezone-aware")

    target = local_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    # Handle day boundary if current time is near midnight and hour is 0/23 edge cases
    # Compute absolute delta
    delta = abs((local_dt - target).total_seconds())
    return delta <= window_minutes * 60
