"""Lead Capture API — Non-Paid Acquisition System (GAR-486).

Endpoints:
  POST /leads                  — capture lead, dedupe by email
  GET  /leads/{lead_id}        — lead + live score + events
  POST /leads/{lead_id}/score  — re-score; triggers conversion if qualified
  POST /leads/{lead_id}/events — log engagement event
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

from core.lead_scorer import score_lead, is_qualified
from integrations.supabase_client import get_client

log = structlog.get_logger()

app = FastAPI(
    title="NEXUS Acquisition API",
    version="1.0.0",
    description="Non-Paid Acquisition System — GAR-486",
)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@garcar.io")
STRIPE_STARTER_PRICE_ID = os.getenv("STRIPE_PRICE_ID_STARTER", "")


# ── Pydantic models ──────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    email: EmailStr
    source: str = "direct"              # organic | referral | direct
    utm_source: str = ""
    utm_medium: str = ""
    first_name: str = ""
    last_name: str = ""


class EventCreate(BaseModel):
    event_type: str
    metadata: dict[str, Any] = {}


# ── POST /leads ──────────────────────────────────────────────────────────────

@app.post("/leads", status_code=201)
async def capture_lead(body: LeadCreate) -> dict:
    """Capture a lead; deduplicates by email."""
    sb = await get_client()

    # Deduplicate
    existing = (
        await sb.table("leads")
        .select("id, email, source, status, score, created_at, updated_at")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    if existing.data:
        log.info("lead_duplicate", email=body.email, id=existing.data["id"])
        return {"lead_id": existing.data["id"], "created": False, "lead": existing.data}

    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": lead_id,
        "email": body.email,
        "source": body.source,
        "utm_source": body.utm_source,
        "utm_medium": body.utm_medium,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "score": 0,
        "status": "new",
        "created_at": now,
        "updated_at": now,
    }
    await sb.table("leads").insert(row).execute()
    log.info("lead_captured", lead_id=lead_id, email=body.email, source=body.source)
    return {"lead_id": lead_id, "created": True, "lead": row}


# ── GET /leads/{lead_id} ─────────────────────────────────────────────────────

@app.get("/leads/{lead_id}")
async def get_lead(lead_id: str) -> dict:
    """Return lead with live score and events."""
    sb = await get_client()

    lead_res = (
        await sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    )
    if not lead_res.data:
        raise HTTPException(status_code=404, detail="Lead not found")

    events_res = (
        await sb.table("lead_events")
        .select("*")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    events = events_res.data or []
    scored = score_lead(lead_res.data, events)
    return {"lead": scored, "events": events}


# ── POST /leads/{lead_id}/score ──────────────────────────────────────────────

@app.post("/leads/{lead_id}/score")
async def rescore_lead(lead_id: str) -> dict:
    """Re-score a lead; triggers conversion flow when score ≥ 70."""
    sb = await get_client()

    lead_res = (
        await sb.table("leads").select("*").eq("id", lead_id).maybe_single().execute()
    )
    if not lead_res.data:
        raise HTTPException(status_code=404, detail="Lead not found")

    events_res = (
        await sb.table("lead_events").select("*").eq("lead_id", lead_id).execute()
    )
    events = events_res.data or []
    scored = score_lead(lead_res.data, events)
    score = scored["score"]

    # Persist updated score
    await (
        sb.table("leads")
        .update({"score": score, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", lead_id)
        .execute()
    )

    triggered = False
    if is_qualified(score) and lead_res.data.get("status") not in ("qualified", "converted"):
        triggered = await _trigger_conversion(sb, lead_res.data, score)

    log.info("lead_rescored", lead_id=lead_id, score=score, triggered=triggered)
    return {"lead_id": lead_id, "score": score, "qualified": is_qualified(score),
            "conversion_triggered": triggered}


# ── POST /leads/{lead_id}/events ─────────────────────────────────────────────

@app.post("/leads/{lead_id}/events", status_code=201)
async def log_lead_event(lead_id: str, body: EventCreate) -> dict:
    """Log an engagement event for a lead."""
    sb = await get_client()

    lead_res = (
        await sb.table("leads").select("id").eq("id", lead_id).maybe_single().execute()
    )
    if not lead_res.data:
        raise HTTPException(status_code=404, detail="Lead not found")

    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": event_id,
        "lead_id": lead_id,
        "event_type": body.event_type,
        "metadata": body.metadata,
        "created_at": now,
    }
    await sb.table("lead_events").insert(row).execute()
    log.info("lead_event_logged", lead_id=lead_id, event_type=body.event_type)
    return {"event_id": event_id, "lead_id": lead_id, "event_type": body.event_type}


# ── Conversion trigger ───────────────────────────────────────────────────────

async def _trigger_conversion(sb: Any, lead: dict, score: int) -> bool:
    """Create Stripe checkout session and send SendGrid outreach email."""
    email = lead["email"]
    checkout_url = ""
    try:
        from integrations.stripe_client import create_payment_link
        checkout_url = await create_payment_link(
            amount_cents=9900,
            description="Garcar Enterprise — Starter Plan",
        )
    except Exception as exc:
        log.warning("stripe_checkout_failed", error=str(exc), email=email)

    try:
        await _send_outreach_email(email, checkout_url, score)
    except Exception as exc:
        log.warning("sendgrid_outreach_failed", error=str(exc), email=email)

    # Mark as qualified and record conversion row
    now = datetime.now(timezone.utc).isoformat()
    await (
        sb.table("leads")
        .update({"status": "qualified", "updated_at": now})
        .eq("id", lead["id"])
        .execute()
    )
    await sb.table("conversions").insert({
        "id": str(uuid.uuid4()),
        "lead_id": lead["id"],
        "stripe_customer_id": "",
        "amount": 9900,
        "plan": "starter",
        "converted_at": now,
        "checkout_url": checkout_url,
    }).execute()
    log.info("conversion_triggered", lead_id=lead["id"], score=score, url=checkout_url)
    return True


async def _send_outreach_email(to_email: str, checkout_url: str, score: int) -> None:
    """Send a personalised outreach email via SendGrid."""
    if not SENDGRID_API_KEY:
        log.info("sendgrid_skipped_no_key", email=to_email)
        return
    import httpx
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": SENDGRID_FROM_EMAIL},
        "subject": "You've been selected — Garcar Enterprise",
        "content": [
            {
                "type": "text/plain",
                "value": (
                    f"Hi,\n\nYour engagement score of {score} qualifies you for "
                    f"Garcar Enterprise.\n\nStart here: {checkout_url}\n\n"
                    "The Garcar Team"
                ),
            }
        ],
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": "******",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        r.raise_for_status()
