"""
Garcar Enterprise — Shopify Revenue Bridge
Echo Revenue Flow: Autonomous product sales, order fulfillment, AI-upsell triggers
"""

import os
import httpx
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = "2024-04"


class ShopifyRevenueBridge:
    """
    Shopify Revenue Bridge — Garcar Enterprise storefront automation.
    Handles:
    - Product listing creation from AI-generated content
    - Order monitoring → Supabase ledger sync
    - Abandoned cart recovery via autonomous email
    - AI-powered upsell recommendation injection
    """

    BASE_URL: str = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}"

    def __init__(self):
        self.headers = {
            "X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json",
        }

    async def get_recent_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent orders for revenue tracking."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/orders.json?status=any&limit={limit}",
                headers=self.headers,
            )
            orders = resp.json().get("orders", [])
            logger.info(f"[SHOPIFY] Fetched {len(orders)} recent orders")
            return orders

    async def get_revenue_summary(self) -> Dict[str, Any]:
        """Compute total revenue from recent orders for gc_ledger."""
        orders = await self.get_recent_orders(250)
        total = sum(float(o.get("total_price", 0)) for o in orders if o.get("financial_status") == "paid")
        logger.info(f"[SHOPIFY] Revenue summary: ${total:,.2f} from {len(orders)} orders")
        return {
            "total_revenue_usd": total,
            "order_count": len(orders),
            "source": "shopify",
        }

    async def create_product(
        self,
        title: str,
        description: str,
        price: float,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Autonomously create a new product listing — AI content injection ready."""
        payload = {
            "product": {
                "title": title,
                "body_html": f"<p>{description}</p>",
                "tags": ",".join(tags or ["garcar", "ai", "enterprise"]),
                "variants": [{"price": str(price), "inventory_management": "shopify"}],
                "status": "active",
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/products.json",
                json=payload,
                headers=self.headers,
            )
            data = resp.json().get("product", {})
            logger.info(f"[SHOPIFY] Product created: {data.get('id')} — {title}")
            return data

    async def trigger_abandoned_cart_recovery(self, checkout_id: str) -> Dict[str, Any]:
        """Send recovery email for abandoned checkout via Shopify."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/checkouts/{checkout_id}/send_invoice.json",
                headers=self.headers,
                json={},
            )
            return resp.json()
