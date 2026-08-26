"""
tests/test_leads.py
15+ tests covering lead capture, scoring, routing, and conversion trigger.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---- import app & scorer ----
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.main import app, _leads, _events
from core.lead_scorer import (
    QUALIFIED_THRESHOLD,
    compute_score,
    is_qualified,
    score_lead,
    _source_weight,
    _engagement_score,
    _recency_score,
)
from core.acquisition import (
    track_github_cta_click,
    receive_linkedin_webhook,
    parse_inbound_email,
    _extract_email_address,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_store():
    """Reset in-memory store between tests."""
    _leads.clear()
    _events.clear()
    yield
    _leads.clear()
    _events.clear()


# ---------------------------------------------------------------------------
# 1. Lead capture — POST /leads
# ---------------------------------------------------------------------------

def test_capture_lead_organic():
    resp = client.post("/leads", json={"email": "alice@example.com", "source": "organic"})
    assert resp.status_code == 201
    assert "lead_id" in resp.json()


def test_capture_lead_referral():
    resp = client.post("/leads", json={"email": "bob@example.com", "source": "referral",
                                        "utm_source": "partner", "utm_medium": "cpc"})
    assert resp.status_code == 201


def test_capture_lead_direct():
    resp = client.post("/leads", json={"email": "carol@example.com", "source": "direct"})
    assert resp.status_code == 201


def test_capture_lead_duplicate_email():
    client.post("/leads", json={"email": "dup@example.com", "source": "direct"})
    resp = client.post("/leads", json={"email": "dup@example.com", "source": "organic"})
    assert resp.status_code == 409


def test_capture_lead_invalid_source():
    resp = client.post("/leads", json={"email": "x@example.com", "source": "twitter"})
    assert resp.status_code == 422


def test_capture_lead_invalid_email():
    resp = client.post("/leads", json={"email": "not-an-email", "source": "direct"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. GET lead
# ---------------------------------------------------------------------------

def test_get_lead_returns_score_and_events():
    lead_id = client.post("/leads", json={"email": "d@ex.com", "source": "organic"}).json()["lead_id"]
    resp = client.get(f"/leads/{lead_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lead_id
    assert "score" in data
    assert "events" in data


def test_get_lead_not_found():
    resp = client.get("/leads/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Scoring — POST /leads/{lead_id}/score
# ---------------------------------------------------------------------------

def test_score_endpoint_returns_breakdown():
    lead_id = client.post("/leads", json={"email": "e@ex.com", "source": "organic"}).json()["lead_id"]
    resp = client.post(f"/leads/{lead_id}/score")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "breakdown" in data


def test_score_increases_with_events():
    lead_id = client.post("/leads", json={"email": "f@ex.com", "source": "organic"}).json()["lead_id"]
    r1 = client.post(f"/leads/{lead_id}/score").json()["score"]
    # Add several events
    for i in range(8):
        client.post(f"/leads/{lead_id}/events", json={"event_type": "page_view"})
    r2 = client.post(f"/leads/{lead_id}/score").json()["score"]
    assert r2 > r1


def test_score_qualified_triggers_conversion():
    """A fresh organic lead with enough events should reach qualified status."""
    lead_id = client.post("/leads", json={"email": "g@ex.com", "source": "organic"}).json()["lead_id"]
    for _ in range(10):
        client.post(f"/leads/{lead_id}/events", json={"event_type": "demo_watched"})
    result = client.post(f"/leads/{lead_id}/score").json()
    assert result["qualified"] is True
    # status should be updated to qualified
    lead_data = client.get(f"/leads/{lead_id}").json()
    assert lead_data["status"] == "qualified"


def test_score_not_found():
    resp = client.post("/leads/00000000-0000-0000-0000-000000000000/score")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Events — POST /leads/{lead_id}/events
# ---------------------------------------------------------------------------

def test_log_event():
    lead_id = client.post("/leads", json={"email": "h@ex.com", "source": "referral"}).json()["lead_id"]
    resp = client.post(f"/leads/{lead_id}/events",
                       json={"event_type": "cta_click", "metadata": {"page": "/pricing"}})
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_type"] == "cta_click"
    assert data["lead_id"] == lead_id


def test_log_event_not_found():
    resp = client.post("/leads/00000000-0000-0000-0000-000000000000/events",
                       json={"event_type": "view"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Scorer unit tests
# ---------------------------------------------------------------------------

def test_source_weight_organic():
    assert _source_weight("organic") == 30

def test_source_weight_referral():
    assert _source_weight("referral") == 20

def test_source_weight_direct():
    assert _source_weight("direct") == 10

def test_engagement_score_cap():
    assert _engagement_score(100) == 40

def test_recency_score_fresh():
    now = datetime.now(timezone.utc)
    assert _recency_score(now) == 30

def test_recency_score_week_old():
    ts = datetime.now(timezone.utc) - timedelta(days=3)
    assert _recency_score(ts) == 20

def test_recency_score_month_old():
    ts = datetime.now(timezone.utc) - timedelta(days=15)
    assert _recency_score(ts) == 10

def test_recency_score_old():
    ts = datetime.now(timezone.utc) - timedelta(days=60)
    assert _recency_score(ts) == 0

def test_compute_score_max():
    now = datetime.now(timezone.utc)
    score = compute_score("organic", 100, now)
    assert score == 100  # 30 + 40 + 30 = 100

def test_compute_score_capped_at_100():
    now = datetime.now(timezone.utc)
    score = compute_score("organic", 200, now)
    assert score <= 100

def test_is_qualified_threshold():
    assert is_qualified(QUALIFIED_THRESHOLD) is True
    assert is_qualified(QUALIFIED_THRESHOLD - 1) is False

def test_score_lead_dict():
    lead = {"source": "organic", "created_at": datetime.now(timezone.utc)}
    events = [{"event_type": "view"} for _ in range(8)]
    result = score_lead(lead, events)
    assert result["score"] == min(100, 30 + 40 + 30)
    assert result["qualified"] is True
    assert "breakdown" in result


# ---------------------------------------------------------------------------
# 6. Acquisition channel tests
# ---------------------------------------------------------------------------

def test_github_cta_returns_utm_params():
    params = track_github_cta_click(utm_campaign="launch")
    assert params["utm_source"] == "github"
    assert params["utm_medium"] == "readme"
    assert params["utm_campaign"] == "launch"


def test_linkedin_webhook_valid():
    payload = {"emailAddress": "li@ex.com", "firstName": "Li", "lastName": "Test",
                "formName": "demo_form"}
    result = receive_linkedin_webhook(payload)
    assert result is not None
    assert result["email"] == "li@ex.com"
    assert result["source"] == "organic"
    assert result["utm_source"] == "linkedin"


def test_linkedin_webhook_missing_email():
    result = receive_linkedin_webhook({"firstName": "No", "lastName": "Email"})
    assert result is None


def test_inbound_email_with_angle_brackets():
    result = parse_inbound_email(
        sender="John Doe <john@example.com>",
        subject="Interested",
        body="I want to learn more.",
    )
    assert result is not None
    assert result["email"] == "john@example.com"
    assert result["source"] == "direct"


def test_inbound_email_bare_address():
    result = parse_inbound_email(
        sender="plain@example.com",
        subject="Hi",
        body="Hello",
    )
    assert result is not None
    assert result["email"] == "plain@example.com"


def test_inbound_email_missing_address():
    result = parse_inbound_email(sender="", subject="S", body="B")
    assert result is None


def test_extract_email_address_angle_brackets():
    from core.acquisition import _extract_email_address
    assert _extract_email_address("Name <addr@x.com>") == "addr@x.com"


def test_extract_email_address_bare():
    from core.acquisition import _extract_email_address
    assert _extract_email_address("addr@x.com") == "addr@x.com"


def test_extract_email_address_empty():
    from core.acquisition import _extract_email_address
    assert _extract_email_address("") is None
