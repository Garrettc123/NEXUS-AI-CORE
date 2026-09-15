"""Engagement agent — closes the 5-minute lead-decay gap.

Breakthrough pattern (2026 agentic GTM):
  sense  -> new lead or engagement signal
  decide -> source-aware sequence + next action
  act    -> SendGrid outreach within seconds (via integrations.sendgrid_client)
  learn  -> log lead_event so scorer compounds

Fires on capture and via always-on scheduler for unengaged leads.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from integrations.sendgrid_client import get_sendgrid
from integrations.supabase_client import get_client

log = structlog.get_logger()

BOOKING_URL = os.getenv("BOOKING_URL", "https://garcar.io/start")

_SEQUENCE: dict[str, dict[str, str]] = {
    "organic": {
        "subject": "You found Garcar — here's the fastest path in",
        "body": (
            "Hi{name_line},\n\n"
            "You came in organically. Most teams waste weeks stitching agents, "
            "billing, and CRM. Garcar Enterprise is the autonomous revenue stack.\n\n"
            "Book 15 minutes or start now: {cta}\n\n"
            "— Garcar Revenue Systems"
        ),
    },
    "referral": {
        "subject": "Your referral path into Garcar Enterprise",
        "body": (
            "Hi{name_line},\n\n"
            "Someone pointed you our way. We run non-paid acquisition → score → "
            "Stripe checkout without human lag.\n\n"
            "Claim your intro slot: {cta}\n\n"
            "— Garcar Revenue Systems"
        ),
    },
    "direct": {
        "subject": "Garcar received your inquiry — next step",
        "body": (
            "Hi{name_line},\n\n"
            "We got your message. Within minutes we score engagement and, "
            "when you qualify, open a checkout path automatically.\n\n"
            "Continue here: {cta}\n\n"
            "— Garcar Revenue Systems"
        ),
    },
}


class EngagementAgent:
    """Instant engagement + always-on backlog processor."""

    async def engage_lead(self, lead: dict[str, Any], *, reason: str = "capture") -> dict:
        lead_id = lead.get("id") or ""
        email = (lead.get("email") or "").strip()
        if not lead_id or not email:
            return {"agent": "EngagementAgent", "status": "skipped", "reason": "missing_id_or_email"}

        source = (lead.get("source") or "direct").lower()
        if source not in _SEQUENCE:
            source = "direct"

        first = (lead.get("first_name") or "").strip()
        name_line = f" {first}" if first else ""
        template = _SEQUENCE[source]
        subject = template["subject"]
        body = template["body"].format(name_line=name_line, cta=BOOKING_URL)

        email_sent = False
        message_id = ""
        try:
            result = await get_sendgrid().send_email(
                to=email,
                subject=subject,
                text=body,
                categories=["engagement", f"source_{source}", reason],
                custom_args={"lead_id": lead_id, "reason": reason},
            )
            email_sent = bool(result.get("ok"))
            message_id = result.get("message_id") or ""
        except Exception as exc:
            log.warning("engagement_email_failed", lead_id=lead_id, error=str(exc))

        event_id = await self._log_event(
            lead_id,
            event_type="engagement_sent",
            metadata={
                "reason": reason,
                "source": source,
                "email_sent": email_sent,
                "channel": "sendgrid" if email_sent else "log_only",
                "subject": subject,
                "message_id": message_id,
            },
        )

        log.info(
            "engagement_fired",
            lead_id=lead_id,
            source=source,
            reason=reason,
            email_sent=email_sent,
            event_id=event_id,
        )
        return {
            "agent": "EngagementAgent",
            "status": "ok",
            "lead_id": lead_id,
            "email_sent": email_sent,
            "event_id": event_id,
            "source": source,
            "reason": reason,
            "message_id": message_id,
        }

    async def run_pending(self) -> dict:
        sb = await get_client()
        resp = (
            await sb.table("leads")
            .select("id, email, source, first_name, last_name, status, score, created_at")
            .eq("status", "new")
            .order("created_at", desc=False)
            .limit(25)
            .execute()
        )
        leads = resp.data or []
        processed = 0
        for lead in leads:
            events_res = (
                await sb.table("lead_events")
                .select("id")
                .eq("lead_id", lead["id"])
                .eq("event_type", "engagement_sent")
                .limit(1)
                .execute()
            )
            if events_res.data:
                continue
            await self.engage_lead(lead, reason="scheduler_backlog")
            processed += 1
        log.info("engagement_agent_tick", processed=processed, scanned=len(leads))
        return {"agent": "EngagementAgent", "status": "ok", "processed": processed}

    async def _log_event(self, lead_id: str, event_type: str, metadata: dict) -> str:
        sb = await get_client()
        event_id = str(uuid.uuid4())
        await sb.table("lead_events").insert(
            {
                "id": event_id,
                "lead_id": lead_id,
                "event_type": event_type,
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        return event_id
