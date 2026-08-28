-- NEXUS-AI-CORE · Non-Paid Acquisition Schema (GAR-486)
-- Run: supabase db push  OR paste into Supabase SQL editor

-- ── Source and status enums ────────────────────────────────────────────────

do $$ begin
  create type lead_source as enum ('organic', 'referral', 'direct');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type lead_status as enum ('new', 'qualified', 'contacted', 'converted', 'lost');
exception when duplicate_object then null;
end $$;

-- ── Leads ──────────────────────────────────────────────────────────────────

create table if not exists leads (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  source      lead_source not null default 'direct',
  utm_source  text not null default '',
  utm_medium  text not null default '',
  first_name  text not null default '',
  last_name   text not null default '',
  score       int  not null default 0 check (score >= 0 and score <= 100),
  status      lead_status not null default 'new',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_leads_email  on leads(email);
create index if not exists idx_leads_source on leads(source);
create index if not exists idx_leads_status on leads(status);
create index if not exists idx_leads_score  on leads(score desc);

-- ── Lead events ────────────────────────────────────────────────────────────

create table if not exists lead_events (
  id          uuid primary key default gen_random_uuid(),
  lead_id     uuid not null references leads(id) on delete cascade,
  event_type  text not null,
  metadata    jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists idx_lead_events_lead_id on lead_events(lead_id);
create index if not exists idx_lead_events_type    on lead_events(event_type);
create index if not exists idx_lead_events_ts      on lead_events(created_at desc);

-- ── Conversions ────────────────────────────────────────────────────────────

create table if not exists conversions (
  id                 uuid primary key default gen_random_uuid(),
  lead_id            uuid not null references leads(id) on delete cascade,
  stripe_customer_id text not null default '',
  amount             int  not null default 0,
  plan               text not null default '',
  checkout_url       text not null default '',
  converted_at       timestamptz not null default now()
);

create index if not exists idx_conversions_lead_id on conversions(lead_id);

-- ── auto-update updated_at trigger ─────────────────────────────────────────

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists leads_updated_at on leads;
create trigger leads_updated_at
  before update on leads
  for each row execute function set_updated_at();

-- ── Row-level security ─────────────────────────────────────────────────────

alter table leads       enable row level security;
alter table lead_events enable row level security;
alter table conversions enable row level security;

do $$ begin
  create policy "service_role_all" on leads
    for all using (auth.role() = 'service_role');
exception when duplicate_object then null;
end $$;

do $$ begin
  create policy "service_role_all" on lead_events
    for all using (auth.role() = 'service_role');
exception when duplicate_object then null;
end $$;

do $$ begin
  create policy "service_role_all" on conversions
    for all using (auth.role() = 'service_role');
exception when duplicate_object then null;
end $$;
