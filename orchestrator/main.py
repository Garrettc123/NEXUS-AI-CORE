"""NEXUS-AI-CORE — FastAPI entry point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import structlog

from orchestrator.router import route_event
from orchestrator.events import NexusEvent

log = structlog.get_logger()

app = FastAPI(
    title="NEXUS-AI-CORE",
    version="2.0.0",
    description="Garcar Enterprise — Autonomous AI Commerce & Real Estate Intelligence Engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nexus-ai-core", "version": "2.0.0"}


# ── Webhook ingest endpoints ─────────────────────────────────────────────────

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    from integrations.stripe_client import verify_and_parse_stripe_webhook
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = verify_and_parse_stripe_webhook(payload, sig)
    result = await route_event(event)
    return {"routed": True, "result": result}


@app.post("/webhooks/shopify")
async def shopify_webhook(request: Request):
    from integrations.shopify_client import verify_and_parse_shopify_webhook
    payload = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "unknown")
    event = verify_and_parse_shopify_webhook(payload, hmac_header, topic)
    result = await route_event(event)
    return {"routed": True, "result": result}


@app.post("/webhooks/hubspot")
async def hubspot_webhook(request: Request):
    body = await request.json()
    for item in body:
        event = NexusEvent(
            source="hubspot",
            type=item.get("subscriptionType", "unknown"),
            intent="crm_update",
            payload=item,
        )
        await route_event(event)
    return {"routed": True}


@app.post("/webhooks/linear")
async def linear_webhook(request: Request):
    body = await request.json()
    event = NexusEvent(
        source="linear",
        type=body.get("type", "unknown"),
        intent="task_update",
        payload=body,
    )
    result = await route_event(event)
    return {"routed": True, "result": result}


@app.post("/webhooks/docusign")
async def docusign_webhook(request: Request):
    body = await request.json()
    event = NexusEvent(
        source="docusign",
        type=body.get("event", "unknown"),
        intent="contract_update",
        payload=body,
    )
    result = await route_event(event)
    return {"routed": True, "result": result}


# ── Manual trigger endpoints ─────────────────────────────────────────────────

@app.post("/agents/score-deal")
async def score_deal(payload: dict):
    from agents.scoring_agent import score_deal_payload
    return await score_deal_payload(payload)


@app.post("/agents/sync-crm")
async def sync_crm(payload: dict):
    from agents.crm_sync_agent import sync_contact
    return await sync_contact(payload)


@app.post("/agents/create-contract")
async def create_contract(payload: dict):
    from agents.contract_agent import create_and_send_contract
    return await create_and_send_contract(payload)
