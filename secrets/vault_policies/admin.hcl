# ── Vault Policy: garcar-admin ──────────────────────────────────────────────
# Full administrative access — Garrettc123 only

path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
