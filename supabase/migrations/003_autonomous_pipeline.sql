-- Autonomous lead/deal/revenue pipeline tables

alter table if exists leads
  add column if not exists name text not null default '',
  add column if not exists property_address text not null default '';

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
