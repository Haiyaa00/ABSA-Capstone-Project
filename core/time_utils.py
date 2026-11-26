"""
Module: time_utils.py
Mo ta: Cac ham tien ich xu ly thoi gian tuong thich Python 3.11+ va SQLite.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Tra ve thoi gian UTC dang naive datetime tuong thich SQLite, tranh deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
