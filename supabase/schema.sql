-- NEXUS-AI-CORE core schema for autonomous lead/deal/revenue pipeline

create extension if not exists pgcrypto;

create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null,
  property_address text not null,
  score int not null default 0 check (score >= 0 and score <= 100),
  created_at timestamptz not null default now()
);

create index if not exists idx_leads_email on leads(email);

create table if not exists deals (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id) on delete cascade,
  stage text not null default 'prospecting',
  notes text not null default '',
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_deals_stage on deals(stage);
create index if not exists idx_deals_updated_at on deals(updated_at desc);

create table if not exists revenue_events (
  id uuid primary key default gen_random_uuid(),
  stripe_event_id text not null unique,
  amount_cents bigint not null default 0,
  event_type text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_revenue_events_created_at on revenue_events(created_at desc);
