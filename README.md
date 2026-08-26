# NEXUS-AI-CORE

**Garcar Enterprise — Autonomous AI Commerce & Real Estate Intelligence Engine**

> Multi-agent orchestration · Stripe revenue loops · Property scoring · Autonomous deal pipeline

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   NEXUS EVENT BUS                       │
│  GitHub · Shopify · Stripe · HubSpot · DocuSign        │
│  Notion · Linear · Supabase · HuggingFace              │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  orchestrator/      │
              │  router.py          │
              │  (classify + route) │
              └──────────┬──────────┘
              ┌──────────▼──────────┐
              │  agents/            │
              │  revenue · deals    │
              │  scoring · outreach │
              └──────────┬──────────┘
              ┌──────────▼──────────┐
              │  integrations/      │
              │  All 8 services     │
              └─────────────────────┘
```

## Services Wired

| Service | Role | Status |
|---|---|---|
| **Shopify** | Product catalog, orders, revenue feed | ✅ Wired |
| **Stripe** | Payments, subscriptions, webhook ingestion | ✅ Wired |
| **HubSpot** | CRM, deal pipeline, contact sync | ✅ Wired |
| **Notion** | System memory, docs, audit log | ✅ Wired |
| **Linear** | Execution ledger, task routing | ✅ Wired |
| **Supabase** | Persistent state, event store, vector search | ✅ Wired |
| **HuggingFace** | Model inference, embedding, scoring | ✅ Wired |
| **DocuSign** | Contract automation, e-sign triggers | ✅ Wired |

## Quick Start

```bash
cp .env.example .env   # fill in all keys
pip install -r requirements.txt
uvicorn orchestrator.main:app --reload
```

## Env Vars

See `.env.example` for all required keys.

## License

Garcar Enterprise — All Rights Reserved
