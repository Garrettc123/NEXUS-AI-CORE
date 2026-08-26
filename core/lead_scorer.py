"""
core/lead_scorer.py
Deterministic lead scoring engine for the Non-Paid Acquisition System.

Score formula (0-100):
  source_weight  : organic=30, referral=20, direct=10
  engagement     : min(event_count * 5, 40)   -> cap at 40
  recency_decay  : 30 if lead < 24 h old, 20 if < 7 d, 10 if < 30 d, 0 otherwise

If final score >= QUALIFIED_THRESHOLD (70) the lead is auto-routed to
the conversion flow.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

QUALIFIED_THRESHOLD = 70

SOURCE_WEIGHTS: dict[str, int] = {
    "organic": 30,
    "referral": 20,
    "direct": 10,
}

MAX_ENGAGEMENT_SCORE = 40
POINTS_PER_EVENT = 5


def _source_weight(source: str) -> int:
    """Return the static weight for a lead source."""
    return SOURCE_WEIGHTS.get(source, 0)


def _engagement_score(event_count: int) -> int:
    """Return an engagement score capped at MAX_ENGAGEMENT_SCORE."""
    return min(event_count * POINTS_PER_EVENT, MAX_ENGAGEMENT_SCORE)


def _recency_score(created_at: datetime) -> int:
    """Return a recency bonus based on how recently the lead was created."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600

    if age_hours < 24:
        return 30
    if age_hours < 24 * 7:
        return 20
    if age_hours < 24 * 30:
        return 10
    return 0


def compute_score(
    source: str,
    event_count: int,
    created_at: datetime,
) -> int:
    """
    Compute a deterministic lead score in the range [0, 100].

    Parameters
    ----------
    source:      Lead acquisition source ('organic' | 'referral' | 'direct').
    event_count: Total number of engagement events logged for this lead.
    created_at:  UTC datetime when the lead was first captured.

    Returns
    -------
    Integer score 0-100.
    """
    raw = (
        _source_weight(source)
        + _engagement_score(event_count)
        + _recency_score(created_at)
    )
    return max(0, min(100, raw))


def is_qualified(score: int) -> bool:
    """Return True if the score meets or exceeds the qualification threshold."""
    return score >= QUALIFIED_THRESHOLD


def score_lead(lead: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Score a lead dict (as returned by Supabase) and return a summary dict.

    Parameters
    ----------
    lead:   Dict with at least 'source' and 'created_at' keys.
    events: List of event dicts for this lead.

    Returns
    -------
    Dict with 'score' (int), 'qualified' (bool), and 'breakdown' (dict).
    """
    source = lead.get("source", "direct")
    created_at = lead.get("created_at", datetime.now(timezone.utc))
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    event_count = len(events)

    sw = _source_weight(source)
    es = _engagement_score(event_count)
    rs = _recency_score(created_at)
    total = max(0, min(100, sw + es + rs))

    return {
        "score": total,
        "qualified": is_qualified(total),
        "breakdown": {
            "source_weight": sw,
            "engagement_score": es,
            "recency_score": rs,
        },
    }
