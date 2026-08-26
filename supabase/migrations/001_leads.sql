-- Migration: 001_leads.sql
-- Non-Paid Acquisition System schema

CREATE TABLE IF NOT EXISTS leads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL UNIQUE,
    source      TEXT NOT NULL CHECK (source IN ('organic', 'referral', 'direct')),
    utm_source  TEXT,
    utm_medium  TEXT,
    score       INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
    status      TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'qualified', 'contacted', 'converted', 'lost')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    stripe_customer_id  TEXT NOT NULL,
    amount              INTEGER NOT NULL,
    plan                TEXT NOT NULL,
    converted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at on leads row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
