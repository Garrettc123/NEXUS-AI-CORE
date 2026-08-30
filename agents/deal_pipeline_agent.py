"""Deal pipeline agent for prospecting -> analysis -> offer -> closed."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import structlog

from integrations.supabase_client import get_client

log = structlog.get_logger()

VALID_STAGES = ("prospecting", "analysis", "offer", "closed")


class DealPipelineAgent:
    async def upsert_deal(
        self,
        lead_id: str,
        stage: str,
        notes: str = "",
        deal_id: str | None = None,
    ) -> dict:
        normalized_stage = stage if stage in VALID_STAGES else "prospecting"
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": deal_id or str(uuid.uuid4()),
            "lead_id": lead_id,
            "stage": normalized_stage,
            "notes": notes,
            "updated_at": now,
        }
        if not deal_id:
            record["created_at"] = now
        sb = await get_client()
        await sb.table("deals").upsert(record, on_conflict="id").execute()
        log.info("deal_upserted", deal_id=record["id"], stage=normalized_stage)
        return record

    async def list_deals(self) -> list[dict]:
        sb = await get_client()
        resp = await sb.table("deals").select("*").order("updated_at", desc=True).execute()
        return resp.data or []

    async def run_pending(self) -> dict:
        deals = await self.list_deals()
        normalized = 0
        sb = await get_client()
        for deal in deals:
            if deal.get("stage") in VALID_STAGES:
                continue
            await (
                sb.table("deals")
                .update(
                    {
                        "stage": "prospecting",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("id", deal["id"])
                .execute()
            )
            normalized += 1
        log.info("deal_pipeline_agent_tick", normalized=normalized)
        return {"agent": "DealPipelineAgent", "status": "ok", "normalized": normalized}
