# NEXUS-AI-CORE — Setup Checklist

Complete these steps in order to activate all integrations.

## 1. Environment

```bash
cp .env.example .env
```

Fill in every value in `.env`. See the table below for where to get each key.

## 2. Service Keys

| Service | Where to get the key | Variable |
|---|---|---|
| **Shopify** | Shopify Admin → Apps → Develop apps → API credentials | `SHOPIFY_ACCESS_TOKEN` |
| **Stripe** | Stripe Dashboard → Developers → API keys | `STRIPE_SECRET_KEY` |
| **Stripe Webhook** | Stripe Dashboard → Developers → Webhooks → Add endpoint | `STRIPE_WEBHOOK_SECRET` |
| **HubSpot** | HubSpot → Settings → Integrations → Private Apps | `HUBSPOT_ACCESS_TOKEN` |
| **Notion** | Notion → Settings → Integrations → Create new integration | `NOTION_API_KEY` |
| **Notion DBs** | Share each DB with your integration; copy the ID from the URL | `NOTION_AUDIT_DB_ID`, `NOTION_MEMORY_DB_ID` |
| **Linear** | Linear → Settings → API → Personal API keys | `LINEAR_API_KEY` |
| **Linear Team** | Linear → Settings → Teams → copy Team ID | `LINEAR_TEAM_ID` |
| **Supabase** | Supabase → Project Settings → API | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| **HuggingFace** | huggingface.co → Settings → Access Tokens | `HUGGINGFACE_API_TOKEN` |
| **DocuSign** | DocuSign Developer → Apps & Keys → Integration Key | `DOCUSIGN_INTEGRATION_KEY` |

## 3. Supabase Schema

```bash
# Option A — Supabase CLI
supabase db push

# Option B — SQL Editor
# Paste contents of supabase/migrations/001_nexus_schema.sql
```

## 4. Notion Databases

Create two databases in Notion and share them with your integration:

**Audit Log** (properties: Event ID [title], Source, Intent, Result, Trace ID [rich text], Timestamp [date])

**Memory** (properties: Key [title], Value, Category [select], Updated [date])

## 5. Webhook Endpoints

Register these URLs in each service's dashboard:

| Service | URL | Events |
|---|---|---|
| Stripe | `https://your-domain.com/webhooks/stripe` | All payment events |
| Shopify | `https://your-domain.com/webhooks/shopify` | Orders, Products, Customers |
| HubSpot | `https://your-domain.com/webhooks/hubspot` | Contact/deal updates |
| Linear | `https://your-domain.com/webhooks/linear` | Issue updates |
| DocuSign | `https://your-domain.com/webhooks/docusign` | Envelope events |

## 6. Run Locally

```bash
pip install -r requirements.txt
uvicorn orchestrator.main:app --reload --port 8000
```

## 7. Deploy

Push to `main` — GitHub Actions will lint, test, and deploy to Railway automatically.

Set `RAILWAY_TOKEN` in your GitHub repo secrets.
