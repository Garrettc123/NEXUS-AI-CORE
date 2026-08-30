"""Revenue loop agent for Stripe payment monitoring and persistence."""
from __future__ import annotations

import os
import uuid

import stripe
import structlog

from integrations.supabase_client import get_client

log = structlog.get_logger()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
TRACKED_EVENTS = {"checkout.session.completed", "payment_intent.succeeded"}


class RevenueLoopAgent:
    async def handle_stripe_event(self, event: dict) -> dict:
        event_type = event.get("type", "")
        if event_type not in TRACKED_EVENTS:
            return {"agent": "RevenueLoopAgent", "status": "ignored", "event_type": event_type}

        payload = event.get("data", {}).get("object", {})
        amount_cents = int(
            payload.get("amount_total")
            or payload.get("amount_received")
            or payload.get("amount")
            or 0
        )
        row = {
            "id": str(uuid.uuid4()),
            "stripe_event_id": event.get("id", ""),
            "amount_cents": amount_cents,
            "event_type": event_type,
        }
        sb = await get_client()
        await sb.table("revenue_events").upsert(row, on_conflict="stripe_event_id").execute()
        log.info("revenue_event_logged", stripe_event_id=row["stripe_event_id"], amount=amount_cents)
        return {"agent": "RevenueLoopAgent", "status": "processed", **row}

    async def poll_recent_payments(self) -> dict:
        events = stripe.Event.list(limit=25, types=list(TRACKED_EVENTS))
        processed = 0
        for event in events.auto_paging_iter():
            result = await self.handle_stripe_event(dict(event))
            if result["status"] == "processed":
                processed += 1
        return {"agent": "RevenueLoopAgent", "status": "ok", "processed": processed}

    async def run_pending(self) -> dict:
        try:
            return await self.poll_recent_payments()
        except Exception as exc:
            log.warning("revenue_poll_failed", error=str(exc))
            return {"agent": "RevenueLoopAgent", "status": "error", "error": str(exc)}
