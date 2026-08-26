"""Linear agent — handles incoming Linear webhook events."""
import structlog
from orchestrator.events import NexusEvent
from integrations import notion_client

log = structlog.get_logger()


async def handle(event: NexusEvent) -> dict:
    payload = event.payload
    issue_id = payload.get("data", {}).get("id", "")
    title = payload.get("data", {}).get("title", "")
    state = payload.get("data", {}).get("state", {}).get("name", "")
    log.info("linear_agent", issue_id=issue_id, state=state)

    try:
        await notion_client.write_memory(
            key=f"linear::{issue_id}",
            value=f"Issue '{title}' transitioned to '{state}'",
            category="tasks",
        )
    except Exception as exc:
        log.warning("notion_write_failed", error=str(exc))

    return {"agent": "linear", "status": "processed",
            "issue_id": issue_id, "state": state}
