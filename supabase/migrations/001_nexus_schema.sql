-- NEXUS-AI-CORE Supabase Schema
-- Run via: supabase db push  or paste into Supabase SQL editor

-- Event log (immutable audit trail)
create table if not exists nexus_events (
  id           text primary key,
  source       text not null,
  type         text not null,
  intent       text not null,
  actor        text,
  trace_id     text not null,
  ts           timestamptz not null default now(),
  payload      jsonb not null default '{}',
  result       jsonb not null default '{}',
  created_at   timestamptz not null default now()
);

create index if not exists idx_nexus_events_source on nexus_events(source);
create index if not exists idx_nexus_events_intent on nexus_events(intent);
create index if not exists idx_nexus_events_ts on nexus_events(ts desc);

-- System state (key-value store)
create table if not exists nexus_state (
  key          text primary key,
  value        jsonb not null default '{}',
  updated_at   timestamptz not null default now()
);

-- Document store with vector embeddings
create extension if not exists vector;

create table if not exists nexus_docs (
  id           uuid primary key default gen_random_uuid(),
  content      text not null,
  metadata     jsonb not null default '{}',
  embedding    vector(384),
  created_at   timestamptz not null default now()
);

-- Vector similarity search function
create or replace function match_documents(
  query_embedding vector(384),
  match_count     int default 5
)
returns table (
  id        uuid,
  content   text,
  metadata  jsonb,
  similarity float
)
language sql stable
as $$
  select id, content, metadata,
         1 - (embedding <=> query_embedding) as similarity
  from nexus_docs
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- Revenue summary view
create or replace view nexus_revenue_summary as
select
  source,
  count(*) as event_count,
  sum((payload->>'amount')::numeric) as total_amount,
  min(ts) as first_event,
  max(ts) as last_event
from nexus_events
where intent = 'revenue'
group by source;

-- Row Level Security
alter table nexus_events enable row level security;
alter table nexus_state enable row level security;
alter table nexus_docs enable row level security;

-- Service role has full access
create policy "service_role_all" on nexus_events
  for all using (auth.role() = 'service_role');
create policy "service_role_all" on nexus_state
  for all using (auth.role() = 'service_role');
create policy "service_role_all" on nexus_docs
  for all using (auth.role() = 'service_role');
