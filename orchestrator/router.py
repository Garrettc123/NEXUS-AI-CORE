"""NEXUS event router — classify intent → dispatch to agent → log."""
import structlog
from orchestrator.events import NexusEvent

log = structlog.get_logger()

# intent → agent function mapping
ROUTING_TABLE: dict[str, str] = {
    "revenue":          "agents.revenue_agent.handle",
    "crm_update":       "agents.crm_sync_agent.handle",
    "task_update":      "agents.linear_agent.handle",
    "contract_update":  "agents.contract_agent.handle",
    "deal":             "agents.scoring_agent.handle",
    "inventory":        "agents.inventory_agent.handle",
    "default":          "agents.fallback_agent.handle",
}


async def route_event(event: NexusEvent) -> dict:
    """Route a NexusEvent to the correct agent and persist the audit record."""
    intent = event.intent
    target = ROUTING_TABLE.get(intent, ROUTING_TABLE["default"])
    log.info("routing_event", event_id=event.id, source=event.source,
             intent=intent, target=target, trace_id=event.trace_id)

    # Lazy-import agent handler
    module_path, fn_name = target.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    handler = getattr(module, fn_name)
    result = await handler(event)

    # Persist audit record to Supabase
    try:
        from integrations.supabase_client import log_event
        await log_event(event, result)
    except Exception as exc:
        log.warning("audit_log_failed", error=str(exc))

    return result
