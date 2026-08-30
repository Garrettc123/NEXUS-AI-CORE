"""Lead scoring agent powered by GPT-4o-mini."""
from __future__ import annotations

import os
import re

import httpx
import structlog

from integrations.supabase_client import get_client

log = structlog.get_logger()


class LeadScoringAgent:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    async def _request_score(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LeadScoringAgent")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": prompt,
                    "max_output_tokens": 20,
                },
            )
            response.raise_for_status()
        data = response.json()
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text", "")
                if text:
                    return text
        return data.get("output_text", "")

    async def score_lead(self, name: str, email: str, property_address: str) -> int:
        prompt = (
            "Score this inbound real-estate lead from 0 to 100 based on purchase "
            "intent, contact quality, and property specificity. Return only an "
            "integer.\n"
            f"Name: {name}\nEmail: {email}\nProperty address: {property_address}"
        )
        text = await self._request_score(prompt)
        match = re.search(r"\d{1,3}", text)
        score = int(match.group(0)) if match else 0
        return max(0, min(score, 100))

    async def run_pending(self) -> dict:
        sb = await get_client()
        resp = await sb.table("leads").select("id,name,email,property_address,score").execute()
        leads = resp.data or []
        processed = 0
        for lead in leads:
            if lead.get("score") not in (None, 0):
                continue
            score = await self.score_lead(
                lead.get("name", ""),
                lead.get("email", ""),
                lead.get("property_address", ""),
            )
            await sb.table("leads").update({"score": score}).eq("id", lead["id"]).execute()
            processed += 1
        log.info("lead_scoring_agent_tick", processed=processed)
        return {"agent": "LeadScoringAgent", "status": "ok", "processed": processed}
