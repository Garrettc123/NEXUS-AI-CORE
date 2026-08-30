"""
integrations/notion_client.py

Notion API client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Database page creation (leads, revenue events, audit logs)
  - Database queries with filters
  - Page content updates
  - Revenue DB logging
  - Memory/audit DB writes
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Notion API client."""

    def __init__(self):
        self._api_key = require_secret(SecretKey.NOTION_API_KEY)
        self._audit_db = get_secret(SecretKey.NOTION_AUDIT_DB_ID)
        self._memory_db = get_secret(SecretKey.NOTION_MEMORY_DB_ID)
        self._revenue_db = get_secret(SecretKey.NOTION_REVENUE_DB_ID)
        self._leads_db = get_secret(SecretKey.NOTION_LEADS_DB_ID)
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        logger.info("[Notion] Client initialised")

    def _post(self, path: str, payload: dict) -> dict:
        r = httpx.post(f"{NOTION_API}{path}", headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()

    def _patch(self, path: str, payload: dict) -> dict:
        r = httpx.patch(f"{NOTION_API}{path}", headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()

    def query_db(self, db_id: str, filter_obj: dict | None = None, sorts: list | None = None) -> list:
        payload: dict = {}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        r = httpx.post(f"{NOTION_API}/databases/{db_id}/query", headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])

    def log_revenue_event(self, source: str, amount: float, currency: str = "USD", notes: str = "") -> dict:
        if not self._revenue_db:
            raise RuntimeError("[Notion] NOTION_REVENUE_DB_ID not configured")
        return self._post("/pages", {
            "parent": {"database_id": self._revenue_db},
            "properties": {
                "Name": {"title": [{"text": {"content": f"{source} — {currency} {amount:,.2f}"}}]},
                "Source": {"rich_text": [{"text": {"content": source}}]},
                "Amount": {"number": amount},
                "Currency": {"rich_text": [{"text": {"content": currency}}]},
                "Date": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                "Notes": {"rich_text": [{"text": {"content": notes}}]},
            },
        })

    def log_audit(self, event: str, details: str = "") -> dict:
        if not self._audit_db:
            raise RuntimeError("[Notion] NOTION_AUDIT_DB_ID not configured")
        return self._post("/pages", {
            "parent": {"database_id": self._audit_db},
            "properties": {
                "Event": {"title": [{"text": {"content": event}}]},
                "Details": {"rich_text": [{"text": {"content": details}}]},
                "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            },
        })

    def upsert_lead(self, name: str, email: str, company: str = "", score: float = 0.0) -> dict:
        if not self._leads_db:
            raise RuntimeError("[Notion] NOTION_LEADS_DB_ID not configured")
        return self._post("/pages", {
            "parent": {"database_id": self._leads_db},
            "properties": {
                "Name": {"title": [{"text": {"content": name}}]},
                "Email": {"email": email},
                "Company": {"rich_text": [{"text": {"content": company}}]},
                "Score": {"number": score},
                "Created": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            },
        })
