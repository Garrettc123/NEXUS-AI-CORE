"""
Garcar Enterprise — Base (Coinbase L2) Integration Client
Echo Revenue Flow: Crypto payment rails, onchain revenue capture, Base smart contract hooks
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
COINBASE_CDP_API_KEY = os.getenv("COINBASE_CDP_API_KEY", "")
COINBASE_CDP_SECRET = os.getenv("COINBASE_CDP_SECRET", "")
GARCAR_WALLET_ADDRESS = os.getenv("GARCAR_WALLET_ADDRESS", "")


class BaseCoinbaseClient:
    """
    Garcar Enterprise — Base L2 & Coinbase CDP client.
    Handles:
    - Onchain revenue capture via Base smart contracts
    - Coinbase Commerce payment webhook processing
    - CDP Wallet creation for autonomous deal closings
    - Base ETH / USDC balance queries for gc_ledger
    """

    def __init__(self):
        self.rpc_url = BASE_RPC_URL
        self.api_key = COINBASE_CDP_API_KEY
        self.secret = COINBASE_CDP_SECRET
        self.wallet_address = GARCAR_WALLET_ADDRESS
        self.headers = {
            "Content-Type": "application/json",
            "CB-ACCESS-KEY": self.api_key,
        }

    async def get_base_balance(self, address: Optional[str] = None) -> Dict[str, Any]:
        """Query ETH + USDC balance on Base L2 for gc_ledger sync."""
        target = address or self.wallet_address
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [target, "latest"],
            "id": 1,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.rpc_url, json=payload)
            result = resp.json()
            wei = int(result.get("result", "0x0"), 16)
            eth_balance = wei / 1e18
            logger.info(f"[BASE] {target} balance: {eth_balance:.6f} ETH")
            return {"address": target, "eth_balance": eth_balance, "wei": wei}

    async def create_payment_charge(
        self,
        amount_usd: float,
        description: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a Coinbase Commerce charge — plugs into Echo Revenue Flow."""
        payload = {
            "name": "Garcar Enterprise Payment",
            "description": description,
            "pricing_type": "fixed_price",
            "local_price": {"amount": str(amount_usd), "currency": "USD"},
            "metadata": metadata or {"source": "nexus-ai-core", "flow": "echo-revenue"},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.commerce.coinbase.com/charges",
                json=payload,
                headers={**self.headers, "X-CC-Api-Key": self.api_key, "X-CC-Version": "2018-03-22"},
            )
            data = resp.json()
            charge_url = data.get("data", {}).get("hosted_url", "")
            charge_id = data.get("data", {}).get("id", "")
            logger.info(f"[BASE] Charge created: {charge_id} — {charge_url}")
            return {"charge_id": charge_id, "url": charge_url, "raw": data}

    async def process_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Coinbase Commerce webhook.
        On charge:confirmed → emit to NEXUS revenue pipeline → update Supabase gc_ledger.
        """
        event_type = event.get("event", {}).get("type", "")
        charge_data = event.get("event", {}).get("data", {})
        amount = charge_data.get("pricing", {}).get("local", {}).get("amount", 0)
        result = {
            "event_type": event_type,
            "amount_usd": float(amount),
            "charge_code": charge_data.get("code", ""),
            "confirmed": event_type == "charge:confirmed",
        }
        if result["confirmed"]:
            logger.info(f"[BASE] 💰 REVENUE CONFIRMED: ${amount} USD onchain")
        return result

    async def get_cdp_wallet(self) -> Dict[str, Any]:
        """Create/retrieve a CDP MPC wallet for autonomous deal execution."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.cdp.coinbase.com/platform/v1/wallets",
                headers=self.headers,
                json={"network_id": "base-mainnet"},
            )
            return resp.json()
