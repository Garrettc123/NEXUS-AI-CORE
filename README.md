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
              │  app/main.py        │
              │  router.py          │
              │  + scheduler loop   │
              └──────────┬──────────┘
              ┌──────────▼──────────┐
              │  agents/            │
              │  LeadScoringAgent   │
              │  DealPipelineAgent  │
              │  PropertyScoring... │
              │  RevenueLoopAgent   │
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

### Autonomous Gateway API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/lead` | Submit lead and return GPT-4o-mini score |
| `POST` | `/deal` | Create/update deal stage in Supabase |
| `GET`  | `/deals` | List all deals and current stage |
| `POST` | `/property/score` | Score property + cap rate estimate |
| `POST` | `/stripe/webhook` | Verify Stripe signature and log revenue event |
| `GET`  | `/health` | Service health check |

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
uvicorn app.main:app --reload
```

## Secrets Reference

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | GPT-4o-mini lead scoring |
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_KEY` | yes | Supabase service key for writes |
| `STRIPE_SECRET_KEY` | yes | Stripe API access |
| `STRIPE_WEBHOOK_SECRET` | yes | Stripe webhook signature verification |
| `PORT` | yes | Runtime port (Railway injects this) |

All required values are listed in `.env.example`.

## License

Garcar Enterprise — All Rights Reserved
