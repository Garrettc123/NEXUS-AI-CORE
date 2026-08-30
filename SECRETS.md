# 🔐 Garcar Enterprise — Secrets Management

**NEXUS-AI-CORE | HashiCorp Vault + GitHub Secrets**

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              GARCAR ENTERPRISE SECRETS LAYER             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────┐   ┌──────────────────────────┐ │
│  │  HashiCorp Vault     │   │  GitHub Actions Secrets  │ │
│  │  (PRIMARY - Prod)    │   │  (BOOTSTRAP ONLY)        │ │
│  │                     │   │                          │ │
│  │  KV v2 engine       │   │  VAULT_ADDR              │ │
│  │  AppRole auth       │   │  VAULT_ROLE_ID           │ │
│  │  Auto-rotation      │   │  VAULT_SECRET_ID         │ │
│  │  Audit logging      │   │  SLACK_ALERTS_CHANNEL    │ │
│  └────────┬────────────┘   └──────────┬───────────────┘ │
│           │                           │                 │
│           └──────────┬────────────────┘                 │
│                      ▼                                  │
│           ┌─────────────────────┐                       │
│           │   SecretsManager    │                       │
│           │   core/secrets_manager.py                   │
│           │                     │                       │
│           │  Priority:          │                       │
│           │  1. Vault KV v2     │                       │
│           │  2. Env vars        │                       │
│           │  3. Default ("")    │                       │
│           └──────────┬──────────┘                       │
│                      │                                  │
│         ┌────────────┼────────────┐                     │
│         ▼            ▼            ▼                     │
│     Stripe      Supabase      HuggingFace               │
│     Base        Notion         Shopify                  │
│     Linear      HubSpot        Slack                    │
└─────────────────────────────────────────────────────────┘
```

---

## Vault Secret Path

```
garcar/data/nexus/echo-revenue-flow
```

All platform secrets live at this single KV v2 path.

---

## GitHub Secrets Required (Bootstrap Only)

Only 4 GitHub repository secrets are needed — Vault holds everything else:

| Secret | Value | Purpose |
|---|---|---|
| `VAULT_ADDR` | `https://vault.garcar.internal` | Vault server URL |
| `VAULT_ROLE_ID` | From bootstrap output | AppRole role ID |
| `VAULT_SECRET_ID` | From bootstrap output | AppRole secret ID |
| `SLACK_ALERTS_CHANNEL` | Slack channel ID | Audit notifications |

---

## Platform Secrets in Vault

| Platform | Vault Key | Purpose |
|---|---|---|
| **Stripe** | `stripe_secret_key` | Payment capture |
| **Stripe** | `stripe_webhook_secret` | Webhook verification |
| **Supabase** | `supabase_url` | gc_ledger database |
| **Supabase** | `supabase_service_key` | Server-side writes |
| **Notion** | `notion_api_key` | Revenue DB pages |
| **Linear** | `linear_api_key` | Fulfillment tasks |
| **HubSpot** | `hubspot_api_key` | CRM deal updates |
| **Shopify** | `shopify_store_domain` | Store URL |
| **Shopify** | `shopify_access_token` | Admin API access |
| **HuggingFace** | `huggingface_api_token` | AI inference |
| **Base/Coinbase** | `coinbase_cdp_api_key` | CDP wallet creation |
| **Base/Coinbase** | `base_rpc_url` | Base L2 RPC |
| **Base/Coinbase** | `garcar_wallet_address` | Revenue wallet |
| **Slack** | `slack_bot_token` | Revenue alerts |
| **GitHub** | `github_token` | Repo automation |

---

## Setup

### Step 1 — Deploy Vault
```bash
# HCP Vault (recommended — managed)
https://portal.cloud.hashicorp.com/sign-up

# Self-hosted on Railway
hashicorp/vault Docker image → Railway → set VAULT_DEV_ROOT_TOKEN_ID
```

### Step 2 — Bootstrap
```bash
export VAULT_ADDR=https://your-vault-url
export VAULT_TOKEN=your-root-token
python -m core.vault_bootstrap
```
Output: `VAULT_ROLE_ID` and `VAULT_SECRET_ID` — add both to GitHub Secrets.

### Step 3 — Populate secrets
```bash
vault kv put garcar/nexus/echo-revenue-flow \
  stripe_secret_key=sk_live_... \
  supabase_url=https://xxx.supabase.co \
  notion_api_key=secret_... \
  # ... all other keys
```

### Step 4 — Verify
```bash
python -c "import asyncio; from core.secrets_manager import secrets; \
  print(asyncio.run(secrets.health_check()))"
```

---

## Usage in Code

```python
from core.secrets_manager import secrets

# Single secret
stripe_key = await secrets.get("STRIPE_SECRET_KEY")

# All secrets for a platform
shopify_secrets = await secrets.get_platform_secrets("shopify")
# → {"SHOPIFY_STORE_DOMAIN": "...", "SHOPIFY_ACCESS_TOKEN": "..."}

# Write/rotate
await secrets.vault_write_secret("HUGGINGFACE_API_TOKEN", new_token)
```

---

*Garcar Enterprise — NEXUS-AI-CORE | Secrets rotate weekly. Audit logs in Vault UI.*
