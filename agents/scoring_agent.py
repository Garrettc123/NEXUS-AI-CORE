"""Deal scoring agent — uses HuggingFace to score and route deals."""
import structlog
from orchestrator.events import NexusEvent
from integrations import huggingface_client, linear_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    payload = event.payload
    features = {
        "company_size": payload.get("company_size", 0),
        "revenue": float(payload.get("annual_revenue", 0)),
        "has_budget": bool(payload.get("budget")),
        "decision_maker": payload.get("role", "") in ["CEO", "CTO", "VP", "Director"],
        "industry": payload.get("industry", ""),
    }
    score = await huggingface_client.score_deal(features)
    log.info("deal_scored", score=score, trace_id=event.trace_id)

    priority = 1 if score > 0.8 else (2 if score > 0.5 else 3)
    try:
        issue = await linear_client.create_issue(
            title=f"[Deal] Score {score:.2f} — {payload.get('company', 'Unknown')}",
            description=f"Score: {score}\nFeatures: {features}\nTrace: {event.trace_id}",
            priority=priority,
        )
    except Exception as exc:
        log.warning("linear_failed", error=str(exc))
        issue = {"error": str(exc)}

    return {"agent": "scoring", "score": score, "priority": priority,
            "linear_issue": issue, "trace_id": event.trace_id}


async def score_deal_payload(payload: dict) -> dict:
    event = NexusEvent(source="manual", type="deal.score",
                       intent="deal", payload=payload)
    return await handle(event)
