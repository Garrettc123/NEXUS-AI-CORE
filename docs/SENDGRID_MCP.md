# SendGrid MCP + NEXUS Client

## Runtime client (gateway / agents)

`integrations/sendgrid_client.py` is the production mail surface:

| Function | Purpose |
|----------|---------|
| `send_email` | Transactional plain/HTML |
| `send_template_email` | Dynamic template by ID |
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

# Capture lead → engagement email if key is set
curl -s -X POST localhost:8000/leads \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","source":"organic","first_name":"Test"}'
```
