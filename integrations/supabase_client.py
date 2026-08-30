"""
integrations/supabase_client.py

Supabase client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Table CRUD (select, insert, update, upsert, delete)
  - RPC (Postgres functions)
  - Realtime subscriptions (via supabase-py)
  - Auth (admin user management)
  - Storage (bucket upload/download)
  - gc_ledger revenue logging
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Supabase client wrapping supabase-py with Vault-resolved credentials."""

    def __init__(self, use_service_role: bool = True):
        self._url = require_secret(SecretKey.SUPABASE_URL)
        key = (
            require_secret(SecretKey.SUPABASE_SERVICE_ROLE_KEY)
            if use_service_role
            else require_secret(SecretKey.SUPABASE_ANON_KEY)
        )
        try:
            from supabase import create_client, Client  # type: ignore
            self._client: Client = create_client(self._url, key)
            logger.info("[Supabase] Client initialised (service_role=%s)", use_service_role)
        except ImportError:
            raise RuntimeError("[Supabase] supabase-py not installed. pip install supabase")

    # ── CRUD ───────────────────────────────────────────────────────────────

    def select(self, table: str, query: str = "*", filters: dict | None = None) -> list:
        req = self._client.table(table).select(query)
        for col, val in (filters or {}).items():
            req = req.eq(col, val)
        return req.execute().data

    def insert(self, table: str, data: dict | list) -> list:
        return self._client.table(table).insert(data).execute().data

    def upsert(self, table: str, data: dict | list, on_conflict: str = "id") -> list:
        return self._client.table(table).upsert(data, on_conflict=on_conflict).execute().data

    def update(self, table: str, match: dict, data: dict) -> list:
        req = self._client.table(table).update(data)
        for col, val in match.items():
            req = req.eq(col, val)
        return req.execute().data

    def delete(self, table: str, match: dict) -> list:
        req = self._client.table(table).delete()
        for col, val in match.items():
            req = req.eq(col, val)
        return req.execute().data

    def rpc(self, fn_name: str, params: dict | None = None) -> Any:
        return self._client.rpc(fn_name, params or {}).execute().data

    # ── Revenue Ledger ─────────────────────────────────────────────────────

    def log_revenue(self, source: str, amount: float, currency: str = "USD", meta: dict | None = None) -> list:
        """Append a row to gc_ledger table."""
        return self.insert("gc_ledger", {
            "source": source,
            "amount": amount,
            "currency": currency,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Storage ────────────────────────────────────────────────────────────

    def upload_file(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
        return self._client.storage.from_(bucket).upload(path, data, {"content-type": content_type})

    def get_public_url(self, bucket: str, path: str) -> str:
        return self._client.storage.from_(bucket).get_public_url(path)
