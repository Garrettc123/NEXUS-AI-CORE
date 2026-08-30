"""
Garcar Enterprise — Secrets Manager
Unified secret resolution: HashiCorp Vault (primary) → GitHub Actions Secrets (fallback) → env vars (dev)

Supports all Echo Revenue Flow platforms:
  GitHub, Slack, Base/Coinbase, Shopify, Notion, Linear, Supabase, HuggingFace
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# --- Vault config ---
VAULT_ADDR    = os.getenv("VAULT_ADDR", "https://vault.garcar.internal")
VAULT_TOKEN   = os.getenv("VAULT_TOKEN", "")          # GitHub secret: VAULT_TOKEN
VAULT_ROLE_ID = os.getenv("VAULT_ROLE_ID", "")        # GitHub secret: VAULT_ROLE_ID
VAULT_SECRET_ID = os.getenv("VAULT_SECRET_ID", "")    # GitHub secret: VAULT_SECRET_ID
VAULT_MOUNT   = os.getenv("VAULT_MOUNT", "garcar")     # KV v2 mount path
VAULT_PATH    = os.getenv("VAULT_SECRET_PATH", "nexus/echo-revenue-flow")


class SecretsManager:
    """
    Garcar Enterprise Secrets Manager

    Resolution priority:
      1. HashiCorp Vault (KV v2)  — production
      2. GitHub Actions ${{ secrets.* }} injected as env vars — CI/CD
      3. .env / process environment — local dev only

    Usage:
        sm = SecretsManager()
        stripe_key = await sm.get("STRIPE_SECRET_KEY")
    """

    # Canonical secret names → Vault KV key names
    SECRET_MAP: Dict[str, str] = {
        # Stripe
        "STRIPE_SECRET_KEY":         "stripe_secret_key",
        "STRIPE_WEBHOOK_SECRET":      "stripe_webhook_secret",
        # Supabase
        "SUPABASE_URL":               "supabase_url",
        "SUPABASE_SERVICE_KEY":       "supabase_service_key",
        "SUPABASE_ANON_KEY":          "supabase_anon_key",
        # Notion
        "NOTION_API_KEY":             "notion_api_key",
        "NOTION_REVENUE_DB_ID":       "notion_revenue_db_id",
        # Linear
        "LINEAR_API_KEY":             "linear_api_key",
        "LINEAR_TEAM_ID":             "linear_team_id",
        # HubSpot
        "HUBSPOT_API_KEY":            "hubspot_api_key",
        # Shopify
        "SHOPIFY_STORE_DOMAIN":       "shopify_store_domain",
        "SHOPIFY_ACCESS_TOKEN":       "shopify_access_token",
        "SHOPIFY_WEBHOOK_SECRET":     "shopify_webhook_secret",
        # HuggingFace
        "HUGGINGFACE_API_TOKEN":      "huggingface_api_token",
        # Base / Coinbase
        "COINBASE_CDP_API_KEY":       "coinbase_cdp_api_key",
        "COINBASE_CDP_SECRET":        "coinbase_cdp_secret",
        "BASE_RPC_URL":               "base_rpc_url",
        "GARCAR_WALLET_ADDRESS":      "garcar_wallet_address",
        # Slack
        "SLACK_BOT_TOKEN":            "slack_bot_token",
        "SLACK_REVENUE_CHANNEL":      "slack_revenue_channel",
        "SLACK_ALERTS_CHANNEL":       "slack_alerts_channel",
        # GitHub
        "GITHUB_TOKEN":               "github_token",
        "GITHUB_ORG":                 "github_org",
        # Vault self-reference (bootstrap only)
        "VAULT_TOKEN":                "vault_token",
    }

    def __init__(self):
        self._vault_token: Optional[str] = VAULT_TOKEN
        self._cache: Dict[str, str] = {}
        self._vault_available: Optional[bool] = None

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def get(self, key: str, default: str = "") -> str:
        """
        Resolve a secret by canonical name.
        Priority: cache → Vault → env var → default
        """
        if key in self._cache:
            return self._cache[key]

        # 1. Try Vault
        vault_key = self.SECRET_MAP.get(key, key.lower())
        value = await self._vault_get(vault_key)
        if value:
            self._cache[key] = value
            logger.debug(f"[SECRETS] {key} resolved from Vault")
            return value

        # 2. Env var fallback (GitHub Actions secrets → env)
        value = os.getenv(key, "")
        if value:
            self._cache[key] = value
            logger.debug(f"[SECRETS] {key} resolved from env")
            return value

        logger.warning(f"[SECRETS] {key} not found in Vault or env")
        return default

    async def get_all(self, keys: list) -> Dict[str, str]:
        """Resolve multiple secrets in one call."""
        result = {}
        for key in keys:
            result[key] = await self.get(key)
        return result

    async def get_platform_secrets(self, platform: str) -> Dict[str, str]:
        """
        Convenience: get all secrets for a given platform.
        platform: 'stripe' | 'supabase' | 'notion' | 'linear' | 'hubspot'
                  'shopify' | 'huggingface' | 'base' | 'slack' | 'github'
        """
        platform_keys = {
            "stripe":       ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
            "supabase":     ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY"],
            "notion":       ["NOTION_API_KEY", "NOTION_REVENUE_DB_ID"],
            "linear":       ["LINEAR_API_KEY", "LINEAR_TEAM_ID"],
            "hubspot":      ["HUBSPOT_API_KEY"],
            "shopify":      ["SHOPIFY_STORE_DOMAIN", "SHOPIFY_ACCESS_TOKEN", "SHOPIFY_WEBHOOK_SECRET"],
            "huggingface":  ["HUGGINGFACE_API_TOKEN"],
            "base":         ["COINBASE_CDP_API_KEY", "COINBASE_CDP_SECRET", "BASE_RPC_URL", "GARCAR_WALLET_ADDRESS"],
            "slack":        ["SLACK_BOT_TOKEN", "SLACK_REVENUE_CHANNEL", "SLACK_ALERTS_CHANNEL"],
            "github":       ["GITHUB_TOKEN", "GITHUB_ORG"],
        }
        keys = platform_keys.get(platform.lower(), [])
        return await self.get_all(keys)

    # ------------------------------------------------------------------ #
    #  HashiCorp Vault — AppRole Auth + KV v2
    # ------------------------------------------------------------------ #

    async def _vault_authenticate(self) -> Optional[str]:
        """
        Authenticate to Vault via AppRole.
        Returns a client token. Caches in self._vault_token.
        """
        if self._vault_token:
            return self._vault_token

        if not VAULT_ROLE_ID or not VAULT_SECRET_ID:
            logger.info("[SECRETS] Vault AppRole credentials not set — skipping Vault auth")
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{VAULT_ADDR}/v1/auth/approle/login",
                    json={"role_id": VAULT_ROLE_ID, "secret_id": VAULT_SECRET_ID},
                )
                data = resp.json()
                token = data.get("auth", {}).get("client_token")
                if token:
                    self._vault_token = token
                    logger.info("[SECRETS] ✅ Vault AppRole authentication successful")
                    return token
        except Exception as e:
            logger.warning(f"[SECRETS] Vault auth failed: {e}")
        return None

    async def _vault_get(self, vault_key: str) -> Optional[str]:
        """
        Read a single key from Vault KV v2.
        Path: {VAULT_MOUNT}/data/{VAULT_PATH}
        """
        token = await self._vault_authenticate()
        if not token:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{VAULT_ADDR}/v1/{VAULT_MOUNT}/data/{VAULT_PATH}",
                    headers={"X-Vault-Token": token},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get("data", {})
                    return data.get(vault_key)
                elif resp.status_code == 403:
                    logger.warning("[SECRETS] Vault permission denied")
                elif resp.status_code == 404:
                    logger.debug(f"[SECRETS] Vault key not found: {vault_key}")
        except Exception as e:
            logger.warning(f"[SECRETS] Vault read error: {e}")
        return None

    async def vault_write_secret(self, key: str, value: str) -> bool:
        """
        Write/rotate a secret in Vault KV v2.
        Used by autonomous secret rotation jobs.
        """
        token = await self._vault_authenticate()
        if not token:
            return False

        vault_key = self.SECRET_MAP.get(key, key.lower())
        try:
            # First read existing data, then patch
            async with httpx.AsyncClient(timeout=10) as client:
                read_resp = await client.get(
                    f"{VAULT_ADDR}/v1/{VAULT_MOUNT}/data/{VAULT_PATH}",
                    headers={"X-Vault-Token": token},
                )
                existing = {}
                if read_resp.status_code == 200:
                    existing = read_resp.json().get("data", {}).get("data", {})

                existing[vault_key] = value
                write_resp = await client.post(
                    f"{VAULT_ADDR}/v1/{VAULT_MOUNT}/data/{VAULT_PATH}",
                    headers={"X-Vault-Token": token},
                    json={"data": existing},
                )
                success = write_resp.status_code in (200, 204)
                if success:
                    # Invalidate cache
                    self._cache.pop(key, None)
                    logger.info(f"[SECRETS] ✅ Vault write success: {key}")
                return success
        except Exception as e:
            logger.error(f"[SECRETS] Vault write error: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check Vault availability and token validity."""
        result = {"vault_addr": VAULT_ADDR, "vault_available": False, "token_valid": False}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{VAULT_ADDR}/v1/sys/health")
                result["vault_available"] = resp.status_code in (200, 429, 472, 473)
                if result["vault_available"] and self._vault_token:
                    lookup = await client.get(
                        f"{VAULT_ADDR}/v1/auth/token/lookup-self",
                        headers={"X-Vault-Token": self._vault_token},
                    )
                    result["token_valid"] = lookup.status_code == 200
        except Exception as e:
            result["error"] = str(e)
        return result


# Singleton — import from anywhere in NEXUS-AI-CORE
secrets = SecretsManager()
