"""CRM sync agent — syncs HubSpot contacts and deals from events."""
import structlog
from orchestrator.events import NexusEvent
from integrations import hubspot_client, notion_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    log.info("crm_sync_agent", event_id=event.id)
    payload = event.payload
    email = payload.get("email") or payload.get("customer", {}).get("email", "")

    if not email:
        return {"agent": "crm_sync", "status": "skipped", "reason": "no email"}

    try:
        result = await hubspot_client.upsert_contact(email, {
            "firstname": payload.get("first_name", ""),
            "lastname": payload.get("last_name", ""),
            "phone": payload.get("phone", ""),
            "nexus_source": event.source,
        })
        log.info("hubspot_upserted", action=result["action"], id=result["id"])
    except Exception as exc:
        log.warning("hubspot_upsert_failed", error=str(exc))
        result = {"action": "error", "error": str(exc)}

    try:
        await notion_client.write_memory(
            key=f"crm::{email}",
            value=f"Synced from {event.source} — {result.get('action')}",
            category="crm",
        )
    except Exception as exc:
        log.warning("notion_write_failed", error=str(exc))

    return {"agent": "crm_sync", "status": "processed",
            "email": email, "hubspot": result}


async def sync_contact(payload: dict) -> dict:
    event = NexusEvent(source="manual", type="contact.sync",
                       intent="crm_update", payload=payload)
    return await handle(event)
