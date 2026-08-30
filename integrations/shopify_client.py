"""
integrations/shopify_client.py

Shopify Admin API client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - Products (list, create, update, inventory)
  - Orders (list, fulfill, refund, cancel)
  - Customers (lookup, create, tag)
  - Revenue summaries
  - Webhook signature verification
  - Storefront API (headless)
"""

import hashlib
import hmac
import logging
from typing import Any, Optional

import httpx

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2025-01"


class ShopifyClient:
    """Shopify Admin REST + Storefront API client."""

    def __init__(self):
        self._domain = require_secret(SecretKey.SHOPIFY_SHOP_DOMAIN)
        self._token = require_secret(SecretKey.SHOPIFY_ACCESS_TOKEN)
        self._webhook_secret = get_secret(SecretKey.SHOPIFY_WEBHOOK_SECRET)
        self._storefront_token = get_secret(SecretKey.SHOPIFY_STOREFRONT_TOKEN)
        self._base = f"https://{self._domain}/admin/api/{SHOPIFY_API_VERSION}"
        self._headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        logger.info("[Shopify] Client initialised (domain=%s)", self._domain)

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = httpx.get(f"{self._base}{path}", headers=self._headers, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict) -> dict:
        r = httpx.post(f"{self._base}{path}", headers=self._headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json()

    # ── Products ───────────────────────────────────────────────────────────

    def list_products(self, limit: int = 50, status: str = "active") -> list:
        return self._get("/products.json", {"limit": limit, "status": status}).get("products", [])

    def create_product(self, title: str, body_html: str, price: str, sku: str, inventory: int = 0) -> dict:
        payload = {"product": {"title": title, "body_html": body_html,
            "variants": [{"price": price, "sku": sku, "inventory_quantity": inventory}]}}
        return self._post("/products.json", payload).get("product", {})

    # ── Orders ─────────────────────────────────────────────────────────────

    def list_orders(self, status: str = "open", limit: int = 50) -> list:
        return self._get("/orders.json", {"status": status, "limit": limit}).get("orders", [])

    def get_order(self, order_id: int) -> dict:
        return self._get(f"/orders/{order_id}.json").get("order", {})

    def revenue_summary(self) -> dict:
        orders = self.list_orders(status="any", limit=250)
        total = sum(float(o.get("total_price", 0)) for o in orders)
        return {"order_count": len(orders), "total_revenue_usd": round(total, 2)}

    # ── Customers ──────────────────────────────────────────────────────────

    def find_customer(self, email: str) -> Optional[dict]:
        customers = self._get("/customers/search.json", {"query": f"email:{email}"}).get("customers", [])
        return customers[0] if customers else None

    # ── Webhooks ───────────────────────────────────────────────────────────

    def verify_webhook(self, payload: bytes, hmac_header: str) -> bool:
        if not self._webhook_secret:
            return False
        import base64
        digest = hmac.new(self._webhook_secret.encode(), payload, hashlib.sha256).digest()
        computed = base64.b64encode(digest).decode()
        return hmac.compare_digest(computed, hmac_header)
