"""Property scoring agent for investment opportunities."""
from __future__ import annotations

import structlog

from integrations.supabase_client import get_client

log = structlog.get_logger()


class PropertyScoringAgent:
    async def score_property(self, address: str, property_data: dict) -> dict:
        annual_rent = float(property_data.get("annual_rent", 0))
        price = float(property_data.get("price", 0))
        annual_expenses = float(property_data.get("annual_expenses", 0))
        noi = max(annual_rent - annual_expenses, 0.0)
        cap_rate = (noi / price) if price > 0 else 0.0

        score = 0
        score += min(int(cap_rate * 1000), 60)
        if property_data.get("bedrooms", 0) >= 3:
            score += 10
        if property_data.get("year_built", 0) >= 2000:
            score += 10
        if property_data.get("neighborhood_grade", "").lower() in {"a", "a+", "b+"}:
            score += 20
        score = max(0, min(score, 100))

        result = {
            "address": address,
            "investment_score": score,
            "cap_rate_estimate": round(cap_rate, 4),
        }
        log.info("property_scored", address=address, score=score, cap_rate=cap_rate)
        return result

    async def run_pending(self) -> dict:
        sb = await get_client()
        deals = await sb.table("deals").select("id").execute()
        tracked = len(deals.data or [])
        log.info("property_scoring_agent_tick", tracked_deals=tracked)
        return {"agent": "PropertyScoringAgent", "status": "ok", "tracked_deals": tracked}
