"""Tests for lead scoring engine and acquisition channels (GAR-486).

Run:  pytest tests/ -v
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from core.lead_scorer import (
    compute_score,
    is_qualified,
    score_lead,
    CONVERSION_THRESHOLD,
)
from core.acquisition import (
    track_github_cta_click,
    receive_linkedin_webhook,
    parse_inbound_email,
    LeadRecord,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _ts(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def _lead(source: str = "organic", created_hours_ago: float = 1.0) -> dict:
    return {
        "id": "lead-1",
        "email": "test@example.com",
        "source": source,
        "status": "new",
        "score": 0,
        "created_at": _ts(created_hours_ago / 24),
    }


def _events(n: int, hours_ago: float = 0.5) -> list[dict]:
    return [{"id": f"ev-{i}", "event_type": "page_view",
             "created_at": _ts(hours_ago / 24)} for i in range(n)]


# ── compute_score ────────────────────────────────────────────────────────────

class TestComputeScore:
    def test_organic_zero_events_recent(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("organic", 0, last)
        # source=30 + engagement=0 + recency=30
        assert score == 60

    def test_referral_source_weight(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("referral", 0, last)
        # source=20 + engagement=0 + recency=30
        assert score == 50

    def test_direct_source_weight(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("direct", 0, last)
        # source=10 + engagement=0 + recency=30
        assert score == 40

    def test_unknown_source_weight(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("unknown", 0, last)
        # source=0 + engagement=0 + recency=30
        assert score == 30

    def test_engagement_capped_at_40(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("organic", 100, last)
        # source=30 + engagement=40(capped) + recency=30 = 100
        assert score == 100

    def test_engagement_partial(self):
        last = datetime.now(timezone.utc) - timedelta(hours=1)
        score = compute_score("organic", 4, last)
        # source=30 + engagement=20 + recency=30 = 80
        assert score == 80

    def test_recency_24h(self):
        last = datetime.now(timezone.utc) - timedelta(hours=2)
        score = compute_score("direct", 0, last)
        assert score == 40  # 10 + 0 + 30

    def test_recency_7d(self):
        last = datetime.now(timezone.utc) - timedelta(days=3)
        score = compute_score("direct", 0, last)
        assert score == 30  # 10 + 0 + 20

    def test_recency_30d(self):
        last = datetime.now(timezone.utc) - timedelta(days=15)
        score = compute_score("direct", 0, last)
        assert score == 20  # 10 + 0 + 10

    def test_recency_old(self):
        last = datetime.now(timezone.utc) - timedelta(days=60)
        score = compute_score("direct", 0, last)
        assert score == 10  # 10 + 0 + 0

    def test_no_last_seen(self):
        score = compute_score("organic", 0, None)
        assert score == 30  # 30 + 0 + 0

    def test_score_capped_at_100(self):
        last = datetime.now(timezone.utc) - timedelta(minutes=5)
        score = compute_score("organic", 50, last)
        assert score == 100

    def test_score_minimum_zero(self):
        score = compute_score("unknown", 0, None)
        assert score == 0


# ── is_qualified ────────────────────────────────────────────────────────────

class TestIsQualified:
    def test_below_threshold(self):
        assert not is_qualified(69)

    def test_at_threshold(self):
        assert is_qualified(CONVERSION_THRESHOLD)

    def test_above_threshold(self):
        assert is_qualified(100)


# ── score_lead ───────────────────────────────────────────────────────────────

class TestScoreLead:
    def test_returns_enriched_dict(self):
        result = score_lead(_lead("organic"), _events(2))
        assert "score" in result
        assert "qualified" in result
        assert "event_count" in result
        assert result["event_count"] == 2

    def test_organic_two_recent_events_qualifies(self):
        result = score_lead(_lead("organic"), _events(2))
        # source=30 + engagement=10 + recency=30 = 70
        assert result["score"] == 70
        assert result["qualified"] is True

    def test_direct_no_events_not_qualified(self):
        result = score_lead(_lead("direct"), [])
        # source=10 + engagement=0 + recency=30 = 40
        assert result["score"] == 40
        assert result["qualified"] is False

    def test_preserves_lead_fields(self):
        lead = _lead("organic")
        result = score_lead(lead, [])
        assert result["email"] == lead["email"]
        assert result["source"] == lead["source"]

    def test_last_seen_from_most_recent_event(self):
        # Recent event should give recency bonus
        result = score_lead(_lead("organic"), _events(1, hours_ago=0.1))
        assert result["score"] >= 60

    def test_fallback_to_created_at(self):
        # No events — uses lead's created_at
        lead = _lead("organic", created_hours_ago=0.5)
        result = score_lead(lead, [])
        assert result["score"] == 60


# ── acquisition: GitHub CTA ─────────────────────────────────────────────────

class TestGitHubCTA:
    def test_returns_utm_params(self):
        result = track_github_cta_click("https://garcar.io/start")
        assert result["utm_source"] == "github"
        assert result["utm_medium"] == "readme"
        assert "full_url" in result

    def test_full_url_contains_base(self):
        result = track_github_cta_click("https://garcar.io/start", campaign="docs")
        assert result["full_url"].startswith("https://garcar.io/start?")

    def test_query_string_parseable(self):
        from urllib.parse import parse_qs
        result = track_github_cta_click("https://garcar.io/start")
        qs = parse_qs(result["query_string"])
        assert qs["utm_source"] == ["github"]
        assert qs["utm_campaign"] == ["readme"]

    def test_custom_campaign(self):
        result = track_github_cta_click("https://garcar.io", campaign="launch")
        assert result["utm_campaign"] == "launch"


# ── acquisition: LinkedIn ────────────────────────────────────────────────────

class TestLinkedIn:
    def _payload(self, email: str = "jane@corp.com",
                 first: str = "Jane", last: str = "Doe") -> dict:
        return {
            "fieldData": [
                {"name": "email_address", "values": [email]},
                {"name": "first_name", "values": [first]},
                {"name": "last_name", "values": [last]},
            ]
        }

    def test_parses_email(self):
        record = receive_linkedin_webhook(self._payload())
        assert record.email == "jane@corp.com"

    def test_parses_name(self):
        record = receive_linkedin_webhook(self._payload())
        assert record.first_name == "Jane"
        assert record.last_name == "Doe"

    def test_source_referral(self):
        record = receive_linkedin_webhook(self._payload())
        assert record.source == "referral"
        assert record.utm_source == "linkedin"

    def test_missing_email_returns_empty(self):
        record = receive_linkedin_webhook({"fieldData": []})
        assert record.email == ""

    def test_raw_payload_preserved(self):
        payload = self._payload()
        record = receive_linkedin_webhook(payload)
        assert record.raw == payload


# ── acquisition: inbound email ───────────────────────────────────────────────

class TestInboundEmail:
    def test_display_name_and_address(self):
        record = parse_inbound_email("John Smith <john@example.com>")
        assert record.email == "john@example.com"
        assert record.first_name == "John"
        assert record.last_name == "Smith"

    def test_bare_address(self):
        record = parse_inbound_email("john@example.com")
        assert record.email == "john@example.com"
        assert record.first_name == ""

    def test_source_direct(self):
        record = parse_inbound_email("x@y.com")
        assert record.source == "direct"
        assert record.utm_medium == "inbound"

    def test_quoted_display_name(self):
        record = parse_inbound_email('"Alice B." <alice@test.org>')
        assert record.email == "alice@test.org"

    def test_fallback_regex(self):
        # bare email with no display name - parseaddr handles this
        record = parse_inbound_email("bob@test.io")
        assert record.email == "bob@test.io"

    def test_returns_lead_record(self):
        record = parse_inbound_email("x@y.com")
        assert isinstance(record, LeadRecord)
