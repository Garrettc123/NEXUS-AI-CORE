"""Revenue agent — handles Stripe + Shopify payment events."""
import structlog
from orchestrator.events import NexusEvent
from integrations import linear_client, notion_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    log.info("revenue_agent", event_id=event.id, type=event.type)
    amount = event.payload.get("amount") or event.payload.get("total_price", 0)
    source = event.source

    # Log to Linear as an automated tracking issue
    try:
        issue = await linear_client.create_issue(
            title=f"[Revenue] {source.capitalize()} event: {event.type}",
            description=f"Amount: {amount}\nTrace: {event.trace_id}\nPayload: {event.payload}",
            priority=3,
        )
        log.info("linear_issue_created", issue_id=issue["id"])
    except Exception as exc:
        log.warning("linear_create_failed", error=str(exc))

    # Write to Notion memory
    try:
        await notion_client.write_memory(
            key=f"revenue::{event.id}",
            value=f"{source} {event.type} amount={amount}",
            category="revenue",
        )
    except Exception as exc:
        log.warning("notion_write_failed", error=str(exc))

    return {"agent": "revenue", "status": "processed", "amount": amount,
            "source": source, "trace_id": event.trace_id}


async def handle_payment_succeeded(payment_intent: dict) -> dict:
    event = NexusEvent(
        source="stripe", type="payment_intent.succeeded",
        intent="revenue", payload=payment_intent
    )
    return await handle(event)
