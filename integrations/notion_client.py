"""Notion integration — system memory, audit log, docs."""
import os
from notion_client import AsyncClient
from datetime import datetime, timezone

_client: AsyncClient | None = None


def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(auth=os.getenv("NOTION_API_KEY", ""))
    return _client


async def append_audit_log(event_id: str, source: str, intent: str,
                            result: str, trace_id: str) -> dict:
    """Append one row to the Notion audit log database."""
    db_id = os.getenv("NOTION_AUDIT_DB_ID", "")
    notion = get_client()
    page = await notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Event ID": {"title": [{"text": {"content": event_id}}]},
            "Source": {"rich_text": [{"text": {"content": source}}]},
            "Intent": {"rich_text": [{"text": {"content": intent}}]},
            "Result": {"rich_text": [{"text": {"content": result}}]},
            "Trace ID": {"rich_text": [{"text": {"content": trace_id}}]},
            "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        },
    )
    return {"page_id": page["id"]}


async def write_memory(key: str, value: str, category: str = "general") -> dict:
    """Write a key-value memory record to Notion memory database."""
    db_id = os.getenv("NOTION_MEMORY_DB_ID", "")
    notion = get_client()
    page = await notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Key": {"title": [{"text": {"content": key}}]},
            "Value": {"rich_text": [{"text": {"content": value}}]},
            "Category": {"select": {"name": category}},
            "Updated": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        },
    )
    return {"page_id": page["id"], "key": key}


async def read_memory(key: str) -> str | None:
    db_id = os.getenv("NOTION_MEMORY_DB_ID", "")
    notion = get_client()
    results = await notion.databases.query(
        database_id=db_id,
        filter={"property": "Key", "rich_text": {"equals": key}},
        sorts=[{"property": "Updated", "direction": "descending"}],
        page_size=1,
    )
    if results["results"]:
        props = results["results"][0]["properties"]
        rt = props.get("Value", {}).get("rich_text", [])
        return rt[0]["text"]["content"] if rt else None
    return None
