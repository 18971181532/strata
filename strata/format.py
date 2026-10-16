"""Human-readable formatting helpers."""
from __future__ import annotations

import time


def human_size(num: float) -> str:
    """Render a byte count as a compact human string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            if unit == "B":
                return f"{int(num)}B"
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PB"


def bar(frac: float, width: int = 28) -> str:
    """A small ASCII progress bar."""
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def time_ago(mtime: float, now: float = None) -> str:
    if now is None:
        now = time.time()
    seconds = max(0, now - mtime)
    intervals = [
        (365 * 24 * 3600, "y"),
        (30 * 24 * 3600, "mo"),
        (7 * 24 * 3600, "w"),
        (24 * 3600, "d"),
        (3600, "h"),
        (60, "m"),
    ]
    for secs, label in intervals:
        if seconds >= secs:
            return f"{int(seconds // secs)}{label}"
    return f"{int(seconds)}s"
