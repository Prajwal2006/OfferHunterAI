-- ============================================================
-- 006_discovery_source_logs.sql
-- Durable per-source observability for Company Finder discovery.
-- ============================================================

create extension if not exists "uuid-ossp";

create table if not exists discovery_source_logs (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  discovery_session_id uuid references discovery_sessions(id) on delete set null,
  source text not null,
  query_used jsonb not null default '[]'::jsonb,
  status text not null default 'running',
  result_count integer not null default 0,
  duplicate_count integer not null default 0,
  filtered_count integer not null default 0,
  error text,
  duration_ms integer,
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table if exists discovery_source_logs
  add constraint discovery_source_logs_status_check
  check (status in ('running', 'success', 'failed', 'timeout'));

create index if not exists idx_discovery_source_logs_user_started
  on discovery_source_logs (user_id, started_at desc);

create index if not exists idx_discovery_source_logs_session
  on discovery_source_logs (discovery_session_id);

alter table discovery_source_logs enable row level security;

create policy "Service role can do everything on discovery_source_logs" on discovery_source_logs
  for all using (true) with check (true);

create policy "Users can read own discovery_source_logs" on discovery_source_logs
  for select using (auth.uid()::text = user_id);
