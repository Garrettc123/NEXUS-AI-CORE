"""
api/main.py
FastAPI application — Non-Paid Acquisition System endpoints.

Endpoints
---------
POST   /leads                    — capture a new lead
GET    /leads/{lead_id}          — retrieve lead with score and events
POST   /leads/{lead_id}/score    — (re-)score a lead
POST   /leads/{lead_id}/events   — log an engagement event
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from core.lead_scorer import QUALIFIED_THRESHOLD, score_lead

app = FastAPI(
    title="NEXUS-AI-CORE Acquisition API",
    version="1.0.0",
    description="Non-Paid Acquisition System — lead capture, scoring, and conversion.",
)

# ---------------------------------------------------------------------------
# In-memory store (replace with Supabase client in production)
# ---------------------------------------------------------------------------
_leads: dict[str, dict[str, Any]] = {}
_events: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

VALID_SOURCES = {"organic", "referral", "direct"}
VALID_STATUSES = {"new", "qualified", "contacted", "converted", "lost"}


class LeadCreate(BaseModel):
    email: EmailStr
    source: str = "direct"
    utm_source: str | None = None
    utm_medium: str | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        return v


class LeadEventCreate(BaseModel):
    event_type: str
    metadata: dict[str, Any] | None = None


class LeadStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_lead_or_404(lead_id: str) -> dict[str, Any]:
    lead = _leads.get(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def _trigger_conversion_flow(lead_id: str, lead: dict[str, Any]) -> None:
    """
    Auto-trigger conversion flow when a lead qualifies.

    In production this would:
      1. Create a Stripe Checkout session.
      2. Send outreach email via SendGrid with the checkout link.

    Here we update the lead status and log a conversion_triggered event.
    """
    if lead["status"] in ("converted", "lost"):
        return

    lead["status"] = "qualified"
    _events.setdefault(lead_id, []).append(
        {
            "id": str(uuid.uuid4()),
            "lead_id": lead_id,
            "event_type": "conversion_triggered",
            "metadata": {
                "stripe_checkout_url": f"https://checkout.stripe.com/pay/stub_{lead_id}",
                "email_sent": True,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/leads", status_code=status.HTTP_201_CREATED)
def capture_lead(body: LeadCreate) -> dict[str, Any]:
    """Capture a new lead with source tracking."""
    for existing in _leads.values():
        if existing["email"] == body.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Lead with this email already exists",
            )

    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    lead: dict[str, Any] = {
        "id": lead_id,
        "email": body.email,
        "source": body.source,
        "utm_source": body.utm_source,
        "utm_medium": body.utm_medium,
        "score": 0,
        "status": "new",
        "created_at": now,
        "updated_at": now,
    }
    _leads[lead_id] = lead
    _events[lead_id] = []
    return {"lead_id": lead_id}


@app.get("/leads/{lead_id}")
def get_lead(lead_id: str) -> dict[str, Any]:
    """Return a lead with its current score and events."""
    lead = _get_lead_or_404(lead_id)
    events = _events.get(lead_id, [])
    scored = score_lead(lead, events)
    return {**lead, **scored, "events": events}


@app.post("/leads/{lead_id}/score")
def score_lead_endpoint(lead_id: str) -> dict[str, Any]:
    """Re-score a lead and auto-route if qualified."""
    lead = _get_lead_or_404(lead_id)
    events = _events.get(lead_id, [])
    result = score_lead(lead, events)
    lead["score"] = result["score"]
    lead["updated_at"] = datetime.now(timezone.utc).isoformat()

    if result["qualified"]:
        _trigger_conversion_flow(lead_id, lead)

    return result


@app.post("/leads/{lead_id}/events", status_code=status.HTTP_201_CREATED)
def log_event(lead_id: str, body: LeadEventCreate) -> dict[str, Any]:
    """Log an engagement event for a lead."""
    _get_lead_or_404(lead_id)
    event: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "event_type": body.event_type,
        "metadata": body.metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _events[lead_id].append(event)
    return event
