# SendGrid MCP + NEXUS Client

## Runtime client (gateway / agents)

`integrations/sendgrid_client.py` is the production mail surface:

| Function | Purpose |
|----------|---------|
| `send_email` | Approval-bound plain/HTML email |
| `send_template_email` | Approval-bound template email |
| `health` | Key present + scopes probe |

Wired into:
- `EngagementAgent` — instant first-touch
- `api/main.py` conversion path — score ≥ 70 checkout email
- `GET /sendgrid/health` — ops probe

Env / Vault:
```
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=noreply@garcar.io
SENDGRID_FROM_NAME=Garcar Enterprise
```

Vault path: `secret/garcar/sendgrid`

## Cursor / Claude MCP server

Project config: `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "sendgrid": {
      "command": "npx",
      "args": ["-y", "mcp-sendgrid-server"],
      "env": {
        "SENDGRID_API_KEY": "${SENDGRID_API_KEY}"
      }
    }
  }
}
```

1. Create a SendGrid API key with **Mail Send** (and templates if needed).
2. Verify sender domain / single sender for `SENDGRID_FROM_EMAIL`.
3. Export `SENDGRID_API_KEY` in the shell that launches Cursor, or put it in `.env`.
4. Restart Cursor MCP so `sendgrid` tools appear.

Alternative (global Cursor config `~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "sendgrid": {
      "command": "npx",
      "args": ["-y", "mcp-sendgrid-server"],
      "env": {
        "SENDGRID_API_KEY": "SG.your-key"
      }
    }
  }
}
```

## Smoke test

```bash
# Gateway probe
curl -s localhost:8000/sendgrid/health

# Capture lead → engagement blocked until an approval decision is redeemed
curl -s -X POST localhost:8000/leads \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","source":"organic","first_name":"Test"}'
```

## Outbound approval redemption (not yet provisioned)

Every mail-send and template-send call requires `policy_decision_id` and a trusted
HTTPS `OUTBOUND_APPROVAL_REDEEM_URL` with a server-only
`OUTBOUND_APPROVAL_SERVICE_TOKEN`. An arbitrary ID never authorizes a send.

The client hashes the exact SendGrid payload with canonical JSON/SHA-256, then
posts the ID, action `sendgrid.send`, and digest to that verification endpoint.
The endpoint must **atomically consume a single-use founder-approved decision**
that is still valid and bound to the requested recipients, action, and payload.
It must return HTTP 200 with `approved: true`, `consumed: true`, and matching
`policy_decision_id`, `action`, and `payload_sha256` fields. A mismatch, replay,
error, absent config, or missing ID blocks sending. The external verifier must
enforce expiry and replay protection; this code does not supply an issuer.

Configuration must be provisioned via secure secrets, not committed to Git.
This change does not deploy an approval service or send customer messages.
Existing NEXUS callers omit `policy_decision_id`, so sends remain blocked until
an approved dispatch path is integrated. `EngagementAgent` records
`engagement_blocked` rather than `engagement_sent` on denied attempts.

Do not deploy as unattended outreach without independent end-to-end
verification of verifier consumption, sender domain, receipts, and ledger.
