# NEXUS-AI-CORE · Secrets & Integration Architecture

## Overview

All credentials for the Garcar Enterprise multiplex are managed through a **dual-backend secrets system**:

| Backend | Used When | Auth Method |
|---|---|---|
| **HashiCorp Vault** (KV v2) | Production / staging | AppRole (role_id + secret_id) |
| **GitHub Actions Secrets** | CI/CD pipelines | Native GHA injection |
| `.env` file | Local development only | Manual |

The resolver priority is: **Vault → Environment → Default**.

---

## Integration Secret Map

| Platform | Vault Path | Key Secrets |
|---|---|---|
| **GitHub** | `secret/garcar/github` | `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET` |
| **Slack** | `secret/garcar/slack` | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_WEBHOOK_URL`, `SLACK_CHANNEL_ALERTS`, `SLACK_CHANNEL_REVENUE` |
| **Base (Coinbase)** | `secret/garcar/base` | `BASE_API_KEY`, `BASE_PRIVATE_KEY`, `BASE_WALLET_ADDRESS`, `CDP_API_KEY_NAME`, `CDP_API_KEY_PRIVATE_KEY` |
| **Shopify** | `secret/garcar/shopify` | `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_WEBHOOK_SECRET`, `SHOPIFY_STOREFRONT_TOKEN` |
| **Notion** | `secret/garcar/notion` | `NOTION_API_KEY`, `NOTION_REVENUE_DB_ID`, `NOTION_LEADS_DB_ID`, `NOTION_MEMORY_DB_ID` |
| **Linear** | `secret/garcar/linear` | `LINEAR_API_KEY`, `LINEAR_TEAM_ID`, `LINEAR_PROJECT_ID`, `LINEAR_WEBHOOK_SECRET` |
| **Supabase** | `secret/garcar/supabase` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` |
| **Hugging Face** | `secret/garcar/huggingface` | `HUGGINGFACE_API_TOKEN`, `HF_SCORE_MODEL`, `HF_SPACE_ID` |
| **Stripe** | `secret/garcar/stripe` | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_*` |
| **OpenAI** | `secret/garcar/openai` | `OPENAI_API_KEY`, `OPENAI_ORG_ID` |
| **HubSpot** | `secret/garcar/hubspot` | `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_PORTAL_ID` |
| **SendGrid** | `secret/garcar/sendgrid` | `SENDGRID_API_KEY` |
| **DocuSign** | `secret/garcar/docusign` | `DOCUSIGN_INTEGRATION_KEY`, `DOCUSIGN_PRIVATE_KEY` |

---

## Quickstart

### 1. Seed Vault (one-time)
```bash
export VAULT_ADDR=https://vault.garcar.io
export VAULT_TOKEN=<your-root-token>
# Fill all env vars, then:
bash secrets/vault_seed.sh
```

### 2. Use in Python
```python
from core.secrets import get_secret, require_secret, SecretKey

# Optional secret
slack_url = get_secret(SecretKey.SLACK_WEBHOOK_URL)

# Required secret — raises RuntimeError if missing
stripe_key = require_secret(SecretKey.STRIPE_SECRET_KEY)

# Audit all missing secrets
from core.secrets import list_missing_secrets
print(list_missing_secrets())
```

### 3. GitHub Actions
Add all secrets at: `https://github.com/Garrettc123/NEXUS-AI-CORE/settings/secrets/actions`

Required secrets to add:
- `GH_PAT` — Personal Access Token (org:read, repo, workflow)
- `VAULT_ROLE_ID` + `VAULT_SECRET_ID` — Vault AppRole credentials
- `VAULT_ADDR` — set as a **variable** (not secret): `https://vault.garcar.io`
- All integration keys listed in the table above

### 4. Vault AppRole Setup
```bash
# Enable AppRole auth
vault auth enable approle

# Write the nexus-app policy
vault policy write nexus-app secrets/vault_policies/nexus_app.hcl

# Create the role
vault write auth/approle/role/nexus-app \
  token_policies="nexus-app" \
  token_ttl="24h" \
  token_max_ttl="168h" \
  secret_id_ttl="0"

# Get credentials
vault read auth/approle/role/nexus-app/role-id
vault write -f auth/approle/role/nexus-app/secret-id
```

---

## Security Notes

- **Never commit real secrets** — `.env` is in `.gitignore`. `vault_seed.sh` contains only env var references.
- **Rotate secrets quarterly** — re-run `vault_seed.sh` with new values after rotation.
- **Audit log** — Vault writes every read/write to stdout (captured by Railway).
- **Least privilege** — the `nexus-app` policy grants read-only on all paths. Only the `garcar-admin` policy has write access.
- **Base/Coinbase private keys** — stored encrypted in Vault. Never log or print `BASE_PRIVATE_KEY` or `CDP_API_KEY_PRIVATE_KEY`.
