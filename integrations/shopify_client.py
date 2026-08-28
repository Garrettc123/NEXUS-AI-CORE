"""Shopify integration — REST Admin API + webhook verification."""
import base64
import hashlib
import hmac
import os
import httpx
from orchestrator.events import NexusEvent

SHOP = os.getenv("SHOPIFY_SHOP_DOMAIN", "")
TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "").encode()
BASE = f"https://{SHOP}/admin/api/2024-07"


def _headers() -> dict:
    return {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}


def verify_and_parse_shopify_webhook(payload: bytes, hmac_header: str, topic: str) -> NexusEvent:
    digest = base64.b64encode(
        hmac.new(SECRET, payload, hashlib.sha256).digest()
    ).decode()
    if not hmac.compare_digest(digest, hmac_header):
        raise ValueError("Shopify HMAC verification failed")
    import orjson
    data = orjson.loads(payload)
    return NexusEvent(source="shopify", type=topic, intent=_classify_shopify(topic), payload=data)


def _classify_shopify(topic: str) -> str:
    if "orders" in topic:
        return "revenue"
    if "products" in topic:
        return "inventory"
    if "customers" in topic:
        return "crm_update"
    return "default"


async def get_products(limit: int = 50) -> list:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/products.json?limit={limit}", headers=_headers())
        r.raise_for_status()
        return r.json().get("products", [])


async def get_orders(status: str = "any", limit: int = 50) -> list:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/orders.json?status={status}&limit={limit}", headers=_headers())
        r.raise_for_status()
        return r.json().get("orders", [])


async def update_product_price(product_id: str, variant_id: str, price: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.put(
            f"{BASE}/variants/{variant_id}.json",
            headers=_headers(),
            json={"variant": {"id": variant_id, "price": price}},
        )
        r.raise_for_status()
        return r.json()
