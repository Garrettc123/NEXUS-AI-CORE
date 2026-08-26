# NEXUS-AI-CORE

**NEXUS: Autonomous AI Commerce & Real Estate Intelligence Engine by Garcar Enterprise**

> Multi-agent orchestration • Stripe revenue loops • Property scoring • Autonomous deal pipeline

---

## 🔗 Unified with APEX-AI-ENGINE

This repository is the **strategic / product identity layer** for Garcar’s autonomous commerce stack.

**Primary implementation lives in:**

➡️ **[APEX-AI-ENGINE](https://github.com/Garrettc123/APEX-AI-ENGINE)**  
Flagship multi-agent system (Scout → Analyst → Executor → Monetizer) with:

- FastAPI + Celery + Redis orchestration
- Stripe revenue loops & subscriptions
- MARS real-estate integration
- Live WebSocket dashboard
- Full GitHub Actions CI/CD + CodeQL Advanced Security
- Railway production deployment

NEXUS provides the high-level vision, naming, and future expansion surface. All production code, agents, revenue automation, and deployments run through **APEX-AI-ENGINE**.

---

## Architecture Alignment

| Layer              | Repo                          | Role                                      |
|--------------------|-------------------------------|-------------------------------------------|
| Vision / Branding  | **NEXUS-AI-CORE** (this repo) | Product identity & future protocol surface |
| Execution Engine   | **APEX-AI-ENGINE**            | Live multi-agent runtime & revenue loops  |
| Master Orchestration | **systems-master-hub**      | Fleet-wide deploy, secrets, evolution     |
| Enterprise Stack   | **garcar-enterprise-production** | Backend, billing, health monitors       |
| Payment Loop       | **garcar-payment-loop**       | Stripe webhook → ledger automation        |

---

## Quick Links

- Production Engine: https://github.com/Garrettc123/APEX-AI-ENGINE
- Master Hub: https://github.com/Garrettc123/systems-master-hub
- Enterprise Production: https://github.com/Garrettc123/garcar-enterprise-production

---

## 🚀 Non-Paid Acquisition System (GAR-486)

Full lead-capture-to-conversion pipeline running inside NEXUS-AI-CORE.

### Flow Diagram

```
GitHub README CTA ─┐
LinkedIn organic   ├──► POST /leads ──► Score Engine ──► score >= 70?
Direct email       ┘         │               │                │
                             │           recency +           YES
                             │           engagement +         │
                             │           source weight        ▼
                             │                        Stripe Checkout
                             │                        SendGrid email
                             ▼
                     GET /leads/{id}   (lead + events + score)
                     POST /leads/{id}/events  (log engagement)
                     POST /leads/{id}/score   (re-score on demand)
```

### Scoring Rules (0-100)

| Component          | Points                                 |
|--------------------|----------------------------------------|
| Source weight      | organic=30, referral=20, direct=10     |
| Engagement events  | events × 5 (max 40)                    |
| Recency bonus      | <24 h=30, <7 d=20, <30 d=10, older=0  |

**Qualified threshold:** score ≥ 70 → auto-trigger Stripe checkout + SendGrid outreach.

### Project Layout

```
supabase/
  migrations/
    001_leads.sql        # leads, lead_events, conversions tables
core/
  lead_scorer.py         # deterministic scoring engine
  acquisition.py         # channel stubs (GitHub, LinkedIn, email)
api/
  main.py                # FastAPI endpoints
tests/
  test_leads.py          # 35 tests
requirements.txt
```

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Apply Supabase migration
supabase db push   # or run 001_leads.sql against your Postgres instance

# 3. Run the API
uvicorn api.main:app --reload

# 4. Run tests
pytest tests/test_leads.py -v
```

### Environment Variables (production)

| Variable                | Description                         |
|-------------------------|-------------------------------------|
| `SUPABASE_URL`          | Supabase project URL                |
| `SUPABASE_SERVICE_KEY`  | Supabase service role key           |
| `STRIPE_SECRET_KEY`     | Stripe secret key for Checkout      |
| `SENDGRID_API_KEY`      | SendGrid API key for outreach email |

---

**Garcar Enterprise © 2026**  
Autonomous revenue. Zero-human ops. Unified under NEXUS + APEX.
