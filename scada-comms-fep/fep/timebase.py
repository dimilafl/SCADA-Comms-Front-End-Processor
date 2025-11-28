"""Timestamp utilities and normalization for SCADA FEP."""

from datetime import datetime, timezone


def now_utc() -> datetime:
    """
    Get current UTC timestamp with timezone awareness.

    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)
