"""Lead Capture API — Non-Paid Acquisition System (GAR-486).

Mounted on the NEXUS gateway via app.main include_router.

End-to-end breakthrough loop:
  POST /leads                  — capture + instant engagement (sub-minute)
  GET  /leads/{lead_id}        — lead + live score + events
  POST /leads/{lead_id}/score  — re-score; score >= 70 -> Stripe + SendGrid
  POST /leads/{lead_id}/events — log event + auto-rescore (learning loop)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from agents.engagement_agent import EngagementAgent
from core.lead_scorer import score_lead, is_qualified
from integrations.sendgrid_client import get_sendgrid
from integrations.supabase_client import get_client

log = structlog.get_logger()

router = APIRouter(tags=["acquisition"])
_engagement = EngagementAgent()


class LeadCreate(BaseModel):
    email: EmailStr
    source: str = "direct"
    utm_source: str = ""
    utm_medium: str = ""
    first_name: str = ""
    last_name: str = ""


class EventCreate(BaseModel):
    event_type: str
    metadata: dict[str, Any] = {}


@router.post("/leads", status_code=201)
async def capture_lead(body: LeadCreate) -> dict:
    """Capture a lead, dedupe by email, fire instant engagement."""
    sb = await get_client()

    existing = (
        await sb.table("leads")
        .select("id, email, source, status, score, created_at, updated_at, first_name, last_name")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    if existing.data:
        log.info("lead_duplicate", email=body.email, id=existing.data["id"])
        engagement = await _engagement.engage_lead(existing.data, reason="duplicate_reengage")
        return {
            "lead_id": existing.data["id"],
            "created": False,
            "lead": existing.data,
            "engagement": engagement,
        }

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

    engagement = await _engagement.engage_lead(row, reason="capture")
    score_result = await _rescore_and_maybe_convert(sb, lead_id)

    return {
        "lead_id": lead_id,
        "created": True,
        "lead": row,
        "engagement": engagement,
        "score": score_result,
    }


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str) -> dict:
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


@router.post("/leads/{lead_id}/score")
async def rescore_lead(lead_id: str) -> dict:
    sb = await get_client()
    return await _rescore_and_maybe_convert(sb, lead_id)


@router.post("/leads/{lead_id}/events", status_code=201)
async def log_lead_event(lead_id: str, body: EventCreate) -> dict:
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

    score_result = await _rescore_and_maybe_convert(sb, lead_id)
    return {
        "event_id": event_id,
        "lead_id": lead_id,
        "event_type": body.event_type,
        "score": score_result,
    }


@router.get("/sendgrid/health")
async def sendgrid_health() -> dict:
    """Probe SendGrid configuration (MCP health surface)."""
    return await get_sendgrid().health()


async def _rescore_and_maybe_convert(sb: Any, lead_id: str) -> dict:
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
    return {
        "lead_id": lead_id,
        "score": score,
        "qualified": is_qualified(score),
        "conversion_triggered": triggered,
    }


async def _trigger_conversion(sb: Any, lead: dict, score: int) -> bool:
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
        await get_sendgrid().send_email(
            to=email,
            subject="You've been selected — Garcar Enterprise",
            text=(
                f"Hi,\n\nYour engagement score of {score} qualifies you for "
                f"Garcar Enterprise.\n\nStart here: {checkout_url}\n\n"
                "The Garcar Team"
            ),
            categories=["conversion", "qualified"],
            custom_args={"lead_id": lead["id"], "score": str(score)},
        )
    except Exception as exc:
        log.warning("sendgrid_outreach_failed", error=str(exc), email=email)

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
