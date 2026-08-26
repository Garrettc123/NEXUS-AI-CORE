"""Inventory agent — handles Shopify product/inventory events."""
import structlog
from orchestrator.events import NexusEvent
from integrations import linear_client, notion_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    payload = event.payload
    product_id = payload.get("id", "")
    title = payload.get("title", "")
    inventory = payload.get("variants", [{}])[0].get("inventory_quantity", None) \
        if payload.get("variants") else None

    log.info("inventory_agent", product_id=product_id, title=title, inventory=inventory)

    if inventory is not None and inventory < 5:
        try:
            await linear_client.create_issue(
                title=f"[Inventory] Low stock: {title} ({inventory} remaining)",
                description=f"Product ID: {product_id}\nTrace: {event.trace_id}",
                priority=2,
            )
        except Exception as exc:
            log.warning("linear_failed", error=str(exc))

    try:
        await notion_client.write_memory(
            key=f"inventory::{product_id}",
            value=f"{title} qty={inventory}",
            category="inventory",
        )
    except Exception as exc:
        log.warning("notion_failed", error=str(exc))

    return {"agent": "inventory", "status": "processed",
            "product_id": product_id, "inventory": inventory}
