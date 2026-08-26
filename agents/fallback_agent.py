"""Fallback agent — handles unclassified events with logging."""
import structlog
from orchestrator.events import NexusEvent
from integrations import notion_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    log.warning("fallback_agent", event_id=event.id, source=event.source,
                type=event.type, intent=event.intent)
    try:
        await notion_client.write_memory(
            key=f"fallback::{event.id}",
            value=f"Unclassified event from {event.source}: {event.type}",
            category="fallback",
        )
    except Exception as exc:
        log.warning("notion_failed", error=str(exc))
    return {"agent": "fallback", "status": "logged",
            "source": event.source, "type": event.type}
