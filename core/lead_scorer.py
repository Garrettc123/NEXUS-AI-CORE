"""Lead scoring engine — deterministic 0-100 formula.

score = source_weight + engagement_bonus + recency_bonus

  source_weight : organic=30, referral=20, direct=10
  engagement    : min(event_count × 5, 40)
  recency       : <24h=30, <7d=20, <30d=10, older=0

Scores ≥ 70 trigger the conversion flow automatically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CONVERSION_THRESHOLD = 70

# ── component weights ────────────────────────────────────────────────────────

SOURCE_WEIGHTS: dict[str, int] = {
    "organic": 30,
    "referral": 20,
    "direct": 10,
}

MAX_ENGAGEMENT_BONUS = 40
ENGAGEMENT_POINTS_PER_EVENT = 5

RECENCY_TIERS: list[tuple[float, int]] = [
    (1.0, 30),    # < 1 day
    (7.0, 20),    # < 7 days
    (30.0, 10),   # < 30 days
]


# ── public API ───────────────────────────────────────────────────────────────

def compute_score(
    source: str,
    event_count: int,
    last_seen_at: datetime | None,
) -> int:
    """Return an integer score 0–100 for a lead."""
    source_w = SOURCE_WEIGHTS.get(source, 0)
    engagement = min(event_count * ENGAGEMENT_POINTS_PER_EVENT, MAX_ENGAGEMENT_BONUS)
    recency = _recency_bonus(last_seen_at)
    return min(source_w + engagement + recency, 100)


def is_qualified(score: int) -> bool:
    """Return True when the score meets or exceeds the conversion threshold."""
    return score >= CONVERSION_THRESHOLD


def score_lead(lead: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a lead dict (as returned by Supabase) and return enriched dict."""
    source = lead.get("source", "direct")
    event_count = len(events)

    # Derive last_seen_at from the most recent event or lead created_at
    last_seen_at: datetime | None = None
    if events:
        event_timestamps = [
            parsed
            for e in events
            if (parsed := _parse_timestamp(e.get("created_at"))) is not None
        ]
        if event_timestamps:
            last_seen_at = max(event_timestamps)
    if last_seen_at is None and lead.get("created_at"):
        last_seen_at = _parse_timestamp(lead.get("created_at"))

    score = compute_score(source, event_count, last_seen_at)
    return {
        **lead,
        "score": score,
        "qualified": is_qualified(score),
        "event_count": event_count,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

def _recency_bonus(last_seen_at: datetime | None) -> int:
    if last_seen_at is None:
        return 0
    now = datetime.now(timezone.utc)
    # Ensure tz-aware comparison
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    days_ago = (now - last_seen_at).total_seconds() / 86400
    for threshold_days, bonus in RECENCY_TIERS:
        if days_ago < threshold_days:
            return bonus
    return 0


def _parse_timestamp(raw_timestamp: Any) -> datetime | None:
    if not isinstance(raw_timestamp, str) or not raw_timestamp:
        return None
    try:
        return datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
