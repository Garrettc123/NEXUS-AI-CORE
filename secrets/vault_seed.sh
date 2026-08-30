#!/usr/bin/env bash
# ── NEXUS-AI-CORE · Vault Seed Script ───────────────────────────────────────
# Seeds all integration secrets into Vault KV v2
# Usage: VAULT_ADDR=https://vault.garcar.io VAULT_TOKEN=<root> bash vault_seed.sh
# WARNING: Fill in real values before running. Never commit with real secrets.

set -euo pipefail

VAULT_PATH="secret/garcar"

echo "[VAULT SEED] Enabling KV v2 engine..."
vault secrets enable -path=secret kv-v2 2>/dev/null || true

echo "[VAULT SEED] Writing GitHub secrets..."
vault kv put $VAULT_PATH/github \
  GITHUB_TOKEN="$GITHUB_TOKEN" \
  GITHUB_ORG="Garrettc123" \
  GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET"

echo "[VAULT SEED] Writing Slack secrets..."
vault kv put $VAULT_PATH/slack \
  SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN" \
  SLACK_SIGNING_SECRET="$SLACK_SIGNING_SECRET" \
  SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
  SLACK_CHANNEL_ALERTS="$SLACK_CHANNEL_ALERTS" \
  SLACK_CHANNEL_REVENUE="$SLACK_CHANNEL_REVENUE"

echo "[VAULT SEED] Writing Base (Coinbase) secrets..."
vault kv put $VAULT_PATH/base \
  BASE_API_KEY="$BASE_API_KEY" \
  BASE_PRIVATE_KEY="$BASE_PRIVATE_KEY" \
  BASE_WALLET_ADDRESS="$BASE_WALLET_ADDRESS" \
  BASE_NETWORK="base-mainnet" \
  CDP_API_KEY_NAME="$CDP_API_KEY_NAME" \
  CDP_API_KEY_PRIVATE_KEY="$CDP_API_KEY_PRIVATE_KEY"

echo "[VAULT SEED] Writing Shopify secrets..."
vault kv put $VAULT_PATH/shopify \
  SHOPIFY_SHOP_DOMAIN="$SHOPIFY_SHOP_DOMAIN" \
  SHOPIFY_ACCESS_TOKEN="$SHOPIFY_ACCESS_TOKEN" \
  SHOPIFY_WEBHOOK_SECRET="$SHOPIFY_WEBHOOK_SECRET" \
  SHOPIFY_API_VERSION="2025-01" \
  SHOPIFY_STOREFRONT_TOKEN="$SHOPIFY_STOREFRONT_TOKEN"

echo "[VAULT SEED] Writing Notion secrets..."
vault kv put $VAULT_PATH/notion \
  NOTION_API_KEY="$NOTION_API_KEY" \
  NOTION_AUDIT_DB_ID="$NOTION_AUDIT_DB_ID" \
  NOTION_MEMORY_DB_ID="$NOTION_MEMORY_DB_ID" \
  NOTION_DOCS_PAGE_ID="$NOTION_DOCS_PAGE_ID" \
  NOTION_REVENUE_DB_ID="$NOTION_REVENUE_DB_ID" \
  NOTION_LEADS_DB_ID="$NOTION_LEADS_DB_ID"

echo "[VAULT SEED] Writing Linear secrets..."
vault kv put $VAULT_PATH/linear \
  LINEAR_API_KEY="$LINEAR_API_KEY" \
  LINEAR_TEAM_ID="$LINEAR_TEAM_ID" \
  LINEAR_PROJECT_ID="$LINEAR_PROJECT_ID" \
  LINEAR_WEBHOOK_SECRET="$LINEAR_WEBHOOK_SECRET"

echo "[VAULT SEED] Writing Supabase secrets..."
vault kv put $VAULT_PATH/supabase \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
  SUPABASE_DB_PASSWORD="$SUPABASE_DB_PASSWORD"

echo "[VAULT SEED] Writing Hugging Face secrets..."
vault kv put $VAULT_PATH/huggingface \
  HUGGINGFACE_API_TOKEN="$HUGGINGFACE_API_TOKEN" \
  HF_EMBED_MODEL="sentence-transformers/all-MiniLM-L6-v2" \
  HF_SCORE_MODEL="Garrettc123/nexus-deal-scorer" \
  HF_SPACE_ID="$HF_SPACE_ID" \
  HF_DATASET_REPO="$HF_DATASET_REPO"

echo "[VAULT SEED] Writing Stripe secrets..."
vault kv put $VAULT_PATH/stripe \
  STRIPE_SECRET_KEY="$STRIPE_SECRET_KEY" \
  STRIPE_WEBHOOK_SECRET="$STRIPE_WEBHOOK_SECRET" \
  STRIPE_PRICE_ID_STARTER="$STRIPE_PRICE_ID_STARTER" \
  STRIPE_PRICE_ID_GROWTH="$STRIPE_PRICE_ID_GROWTH" \
  STRIPE_PRICE_ID_ENTERPRISE="$STRIPE_PRICE_ID_ENTERPRISE"

echo "[VAULT SEED] Writing OpenAI secrets..."
vault kv put $VAULT_PATH/openai \
  OPENAI_API_KEY="$OPENAI_API_KEY" \
  OPENAI_ORG_ID="$OPENAI_ORG_ID"

echo "[VAULT SEED] Writing HubSpot secrets..."
vault kv put $VAULT_PATH/hubspot \
  HUBSPOT_ACCESS_TOKEN="$HUBSPOT_ACCESS_TOKEN" \
  HUBSPOT_PORTAL_ID="$HUBSPOT_PORTAL_ID" \
  HUBSPOT_WEBHOOK_SECRET="$HUBSPOT_WEBHOOK_SECRET"

echo "[VAULT SEED] Writing SendGrid secrets..."
vault kv put $VAULT_PATH/sendgrid \
  SENDGRID_API_KEY="$SENDGRID_API_KEY" \
  SENDGRID_FROM_EMAIL="noreply@garcar.io"

echo "[VAULT SEED] Writing DocuSign secrets..."
vault kv put $VAULT_PATH/docusign \
  DOCUSIGN_INTEGRATION_KEY="$DOCUSIGN_INTEGRATION_KEY" \
  DOCUSIGN_USER_ID="$DOCUSIGN_USER_ID" \
  DOCUSIGN_ACCOUNT_ID="$DOCUSIGN_ACCOUNT_ID" \
  DOCUSIGN_BASE_URL="$DOCUSIGN_BASE_URL" \
  DOCUSIGN_PRIVATE_KEY="$DOCUSIGN_PRIVATE_KEY"

echo "[VAULT SEED] ✅ All secrets seeded into Vault at $VAULT_PATH"
echo "[VAULT SEED] Run 'vault kv list secret/garcar' to verify."
