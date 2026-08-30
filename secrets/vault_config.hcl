# ── NEXUS-AI-CORE · HashiCorp Vault Configuration ──────────────────────────
# Primary secrets backend for all Garcar Enterprise integrations
# Vault OSS / HCP Vault compatible

# Storage backend — Supabase Postgres via integrated storage
storage "postgresql" {
  connection_url = "$VAULT_PG_CONN_STR"
  table          = "vault_kv_store"
  ha_enabled     = "true"
  ha_table       = "vault_ha_locks"
}

# TCP Listener
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = false
  tls_cert_file = "/vault/tls/vault.crt"
  tls_key_file  = "/vault/tls/vault.key"
}

# Auto-unseal via AWS KMS (or replace with GCP/Azure)
seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "$VAULT_KMS_KEY_ID"
}

# Core config
ui             = true
cluster_name   = "nexus-garcar-prod"
default_lease_ttl = "24h"
max_lease_ttl     = "168h"
raw_storage_endpoint = false
disable_mlock  = true
log_level      = "info"
log_format     = "json"

# Audit log — write to stdout for Railway/Render capture
audit "file" {
  file_path = "stdout"
  log_raw   = false
}
