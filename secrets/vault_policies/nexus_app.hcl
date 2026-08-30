# ── Vault Policy: nexus-app ──────────────────────────────────────────────────
# Grants NEXUS-AI-CORE runtime access to all integration secrets

# GitHub
path "secret/data/garcar/github/*" {
  capabilities = ["read"]
}

# Slack
path "secret/data/garcar/slack/*" {
  capabilities = ["read"]
}

# Base / Coinbase
path "secret/data/garcar/base/*" {
  capabilities = ["read"]
}

# Shopify
path "secret/data/garcar/shopify/*" {
  capabilities = ["read", "list"]
}

# Notion
path "secret/data/garcar/notion/*" {
  capabilities = ["read"]
}

# Linear
path "secret/data/garcar/linear/*" {
  capabilities = ["read"]
}

# Supabase
path "secret/data/garcar/supabase/*" {
  capabilities = ["read"]
}

# Hugging Face
path "secret/data/garcar/huggingface/*" {
  capabilities = ["read"]
}

# Stripe
path "secret/data/garcar/stripe/*" {
  capabilities = ["read"]
}

# OpenAI
path "secret/data/garcar/openai/*" {
  capabilities = ["read"]
}

# SendGrid
path "secret/data/garcar/sendgrid/*" {
  capabilities = ["read"]
}

# DocuSign
path "secret/data/garcar/docusign/*" {
  capabilities = ["read"]
}

# HubSpot
path "secret/data/garcar/hubspot/*" {
  capabilities = ["read"]
}

# Allow token renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow token lookup
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
