"""Supabase integration — persistent state, event store, vector search."""
import os
from supabase import acreate_client, AsyncClient
from orchestrator.events import NexusEvent

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        supabase_key = os.getenv("SUPABASE_KEY", "") or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY", ""
        )
        _client = await acreate_client(
            os.getenv("SUPABASE_URL", ""),
            supabase_key,
        )
    return _client


async def log_event(event: NexusEvent, result: dict) -> None:
    sb = await get_client()
    await sb.table("nexus_events").insert({
        "id": event.id,
        "source": event.source,
        "type": event.type,
        "intent": event.intent,
        "actor": event.actor,
        "trace_id": event.trace_id,
        "ts": event.ts,
        "payload": event.payload,
        "result": result,
    }).execute()


async def upsert_state(key: str, value: dict) -> None:
    sb = await get_client()
    await sb.table("nexus_state").upsert(
        {"key": key, "value": value}, on_conflict="key"
    ).execute()


async def get_state(key: str) -> dict | None:
    sb = await get_client()
    r = await sb.table("nexus_state").select("value").eq("key", key).maybe_single().execute()
    return r.data["value"] if r.data else None


async def vector_search(query_embedding: list[float], table: str = "nexus_docs",
                         match_count: int = 5) -> list:
    sb = await get_client()
    r = await sb.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": match_count,
    }).execute()
    return r.data or []
