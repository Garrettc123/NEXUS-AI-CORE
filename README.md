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

## Non-Paid Acquisition System (GAR-486)

Lead capture-to-conversion pipeline for organic, referral, and direct channels.

### Lead Scoring Formula

```
score = source_weight + engagement_bonus + recency_bonus   (capped 0–100)

  source_weight  : organic=30 · referral=20 · direct=10
  engagement     : min(event_count × 5, 40)
  recency        : <24h=30 · <7d=20 · <30d=10 · older=0
```

Score ≥ 70 → auto-creates Stripe checkout + sends SendGrid outreach email.

### Acquisition API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/leads` | Capture lead (dedupes by email) |
| `GET`  | `/leads/{id}` | Lead + live score + events |
| `POST` | `/leads/{id}/score` | Re-score; triggers conversion if qualified |
| `POST` | `/leads/{id}/events` | Log engagement event |

### Channels

| Channel | Module | Description |
|---------|--------|-------------|
| GitHub README CTA | `core/acquisition.py` | UTM-tagged outbound link params |
| LinkedIn Lead Gen | `core/acquisition.py` | Webhook payload normaliser |
| Inbound email | `core/acquisition.py` | RFC 2822 From header parser |

### Additional Setup

```bash
SENDGRID_API_KEY=SG.xxxx
SENDGRID_FROM_EMAIL=noreply@garcar.io
STRIPE_PRICE_ID_STARTER=price_xxxx
```

---

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
