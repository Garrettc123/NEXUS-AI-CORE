"""NEXUS-AI-CORE autonomous commerce and real-estate gateway."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr
import stripe

from agents.deal_pipeline_agent import DealPipelineAgent
from agents.lead_scoring_agent import LeadScoringAgent
from agents.property_scoring_agent import PropertyScoringAgent
from agents.revenue_loop_agent import RevenueLoopAgent
from integrations.supabase_client import get_client

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


class LeadRequest(BaseModel):
    name: str
    email: EmailStr
    property_address: str


class DealRequest(BaseModel):
    lead_id: str
    stage: str
    notes: str = ""
    id: str | None = None


class PropertyScoreRequest(BaseModel):
    address: str
    property_data: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.lead_scoring_agent = LeadScoringAgent()
    app.state.deal_pipeline_agent = DealPipelineAgent()
    app.state.property_scoring_agent = PropertyScoringAgent()
    app.state.revenue_loop_agent = RevenueLoopAgent()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(app.state.lead_scoring_agent.run_pending, "interval", minutes=3)
    scheduler.add_job(app.state.deal_pipeline_agent.run_pending, "interval", minutes=5)
    scheduler.add_job(app.state.property_scoring_agent.run_pending, "interval", minutes=7)
    scheduler.add_job(app.state.revenue_loop_agent.run_pending, "interval", minutes=2)
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="NEXUS-AI-CORE Gateway",
    version="3.0.0",
    lifespan=lifespan,
)


@app.post("/lead")
async def submit_lead(body: LeadRequest) -> dict:
    score = await app.state.lead_scoring_agent.score_lead(
        body.name,
        body.email,
        body.property_address,
    )
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "email": body.email,
        "property_address": body.property_address,
        "score": score,
        "created_at": now,
    }
    sb = await get_client()
    await sb.table("leads").insert(row).execute()
    return row


@app.post("/deal")
async def create_or_update_deal(body: DealRequest) -> dict:
    return await app.state.deal_pipeline_agent.upsert_deal(
        lead_id=body.lead_id,
        stage=body.stage,
        notes=body.notes,
        deal_id=body.id,
    )


@app.get("/deals")
async def list_deals() -> list[dict]:
    return await app.state.deal_pipeline_agent.list_deals()


@app.post("/property/score")
async def score_property(body: PropertyScoreRequest) -> dict:
    return await app.state.property_scoring_agent.score_property(
        address=body.address,
        property_data=body.property_data,
    )


@app.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
) -> dict:
    payload = await request.body()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe signature: {exc}") from exc
    result = await app.state.revenue_loop_agent.handle_stripe_event(event)
    return {"received": True, "result": result}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "nexus-ai-core"}
