"""
Garcar Enterprise — Vault Bootstrap
Initializes HashiCorp Vault with all Garcar Enterprise secret paths,
policies, and AppRole configuration for NEXUS-AI-CORE.

Run once during infrastructure setup:
  python -m core.vault_bootstrap

Requires: VAULT_ADDR + VAULT_TOKEN (root/admin token) set in environment.
"""

import asyncio
import os
import httpx
import logging

logger = logging.getLogger(__name__)

VAULT_ADDR  = os.getenv("VAULT_ADDR", "https://vault.garcar.internal")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")  # Root/admin token for bootstrap only
VAULT_MOUNT = os.getenv("VAULT_MOUNT", "garcar")

# Vault policy: NEXUS-AI-CORE read/write on garcar/* paths
NEXUS_POLICY = """
path "garcar/data/*" {
  capabilities = ["create", "read", "update", "list"]
}
path "garcar/metadata/*" {
  capabilities = ["read", "list"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "sys/leases/renew" {
  capabilities = ["update"]
}
"""

# Initial secret structure — populate with real values via Vault UI or vault CLI
INITIAL_SECRETS = {
    # --- Stripe ---
    "stripe_secret_key":        "sk_live_REPLACE_ME",
    "stripe_webhook_secret":    "whsec_REPLACE_ME",
    # --- Supabase ---
    "supabase_url":             "https://REPLACE_ME.supabase.co",
    "supabase_service_key":     "REPLACE_ME",
    "supabase_anon_key":        "REPLACE_ME",
    # --- Notion ---
    "notion_api_key":           "secret_REPLACE_ME",
    "notion_revenue_db_id":     "REPLACE_ME",
    # --- Linear ---
    "linear_api_key":           "lin_api_REPLACE_ME",
    "linear_team_id":           "REPLACE_ME",
    # --- HubSpot ---
    "hubspot_api_key":          "REPLACE_ME",
    # --- Shopify ---
    "shopify_store_domain":     "garcar.myshopify.com",
    "shopify_access_token":     "shpat_REPLACE_ME",
    "shopify_webhook_secret":   "REPLACE_ME",
    # --- HuggingFace ---
    "huggingface_api_token":    "hf_REPLACE_ME",
    # --- Base / Coinbase ---
    "coinbase_cdp_api_key":     "REPLACE_ME",
    "coinbase_cdp_secret":      "REPLACE_ME",
    "base_rpc_url":             "https://mainnet.base.org",
    "garcar_wallet_address":    "0xREPLACE_ME",
    # --- Slack ---
    "slack_bot_token":          "xoxb-REPLACE_ME",
    "slack_revenue_channel":    "C_REPLACE_ME",
    "slack_alerts_channel":     "C_REPLACE_ME",
    # --- GitHub ---
    "github_token":             "ghp_REPLACE_ME",
    "github_org":               "Garrettc123",
}


async def bootstrap_vault():
    headers = {"X-Vault-Token": VAULT_TOKEN, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:

        # 1. Enable KV v2 secrets engine at 'garcar/'
        logger.info("[VAULT] Enabling KV v2 engine at garcar/...")
        await client.post(
            f"{VAULT_ADDR}/v1/sys/mounts/{VAULT_MOUNT}",
            headers=headers,
            json={"type": "kv", "options": {"version": "2"}},
        )

        # 2. Write policy
        logger.info("[VAULT] Writing nexus-ai-core policy...")
        await client.put(
            f"{VAULT_ADDR}/v1/sys/policies/acl/nexus-ai-core",
            headers=headers,
            json={"policy": NEXUS_POLICY},
        )

        # 3. Enable AppRole auth
        logger.info("[VAULT] Enabling AppRole auth method...")
        await client.post(
            f"{VAULT_ADDR}/v1/sys/auth/approle",
            headers=headers,
            json={"type": "approle"},
        )

        # 4. Create nexus-ai-core AppRole
        logger.info("[VAULT] Creating nexus-ai-core AppRole...")
        await client.post(
            f"{VAULT_ADDR}/v1/auth/approle/role/nexus-ai-core",
            headers=headers,
            json={
                "policies": ["nexus-ai-core"],
                "token_ttl": "1h",
                "token_max_ttl": "4h",
                "secret_id_ttl": "0",  # Never expire secret_id
                "bind_secret_id": True,
            },
        )

        # 5. Write initial secrets
        logger.info("[VAULT] Writing initial secrets to garcar/nexus/echo-revenue-flow...")
        await client.post(
            f"{VAULT_ADDR}/v1/{VAULT_MOUNT}/data/nexus/echo-revenue-flow",
            headers=headers,
            json={"data": INITIAL_SECRETS},
        )

        # 6. Fetch RoleID for GitHub Actions secret
        role_resp = await client.get(
            f"{VAULT_ADDR}/v1/auth/approle/role/nexus-ai-core/role-id",
            headers=headers,
        )
        role_id = role_resp.json().get("data", {}).get("role_id", "")

        # 7. Generate SecretID
        secret_resp = await client.post(
            f"{VAULT_ADDR}/v1/auth/approle/role/nexus-ai-core/secret-id",
            headers=headers,
            json={},
        )
        secret_id = secret_resp.json().get("data", {}).get("secret_id", "")

        logger.info("[VAULT] ✅ Bootstrap complete!")
        logger.info(f"[VAULT] Add to GitHub Secrets:")
        logger.info(f"  VAULT_ADDR     = {VAULT_ADDR}")
        logger.info(f"  VAULT_ROLE_ID  = {role_id}")
        logger.info(f"  VAULT_SECRET_ID = {secret_id}")
        print(f"\nVAULT_ADDR={VAULT_ADDR}")
        print(f"VAULT_ROLE_ID={role_id}")
        print(f"VAULT_SECRET_ID={secret_id}")
        return {"role_id": role_id, "secret_id": secret_id}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(bootstrap_vault())
