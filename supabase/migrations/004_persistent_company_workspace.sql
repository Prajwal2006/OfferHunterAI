-- ============================================================
-- 004_persistent_company_workspace.sql
-- Persistent company workspace, feedback memory, and orchestration state.
-- ============================================================

-- Ensure UUID helpers exist (001 uses uuid-ossp, keep compatibility)
create extension if not exists "uuid-ossp";

-- -----------------------------------------------------------------
-- discovery_sessions: extend with snapshot/version metadata
-- -----------------------------------------------------------------
alter table if exists discovery_sessions
  add column if not exists preferences_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists total_companies_found integer not null default 0,
  add column if not exists sources_used jsonb not null default '[]'::jsonb,
  add column if not exists embedding_version text not null default 'text-embedding-3-small',
  add column if not exists started_at timestamptz not null default now(),
  add column if not exists completed_at timestamptz,
  add column if not exists status text not null default 'running';

alter table if exists discovery_sessions
  add constraint discovery_sessions_status_check
  check (status in ('running', 'completed', 'failed', 'paused'));

create index if not exists idx_discovery_sessions_user_started_at
  on discovery_sessions (user_id, started_at desc);

-- -----------------------------------------------------------------
-- orchestration_state: user-level long-running orchestration memory
-- -----------------------------------------------------------------
create table if not exists orchestration_state (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null unique,
  current_stage text not null default 'CompanyFinder',
  progress jsonb not null default '{}'::jsonb,
  active_agents jsonb not null default '[]'::jsonb,
  paused_state boolean not null default false,
  last_task_id text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_orchestration_state_updated_at
  on orchestration_state (updated_at desc);

-- -----------------------------------------------------------------
-- user_companies: persistent user-company workspace state
-- -----------------------------------------------------------------
create table if not exists user_companies (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  company_id uuid not null references companies(id) on delete cascade,
  discovery_session_id uuid references discovery_sessions(id) on delete set null,
  source text,
  discovered_at timestamptz not null default now(),
  status text not null default 'active',
  orchestration_stage text not null default 'CompanyFinder',
  liked boolean,
  disliked boolean,
  archived boolean not null default false,
  removed boolean not null default false,
  manually_added boolean not null default false,
  personalization_completed boolean not null default false,
  outreach_started boolean not null default false,
  outreach_sent boolean not null default false,
  notes text,
  ranking_score float,
  ranking_explanation text,
  ranking_metadata jsonb not null default '{}'::jsonb,
  application_strategy text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, company_id)
);

create index if not exists idx_user_companies_user_updated
  on user_companies (user_id, updated_at desc);
create index if not exists idx_user_companies_user_stage
  on user_companies (user_id, orchestration_stage);
create index if not exists idx_user_companies_user_flags
  on user_companies (user_id, archived, removed);
create index if not exists idx_user_companies_user_score
  on user_companies (user_id, ranking_score desc nulls last);

-- -----------------------------------------------------------------
-- company_feedback: explicit preference signals
-- -----------------------------------------------------------------
create table if not exists company_feedback (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  company_id uuid not null references companies(id) on delete cascade,
  feedback_type text not null,
  feedback_reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, company_id, feedback_type)
);

alter table if exists company_feedback
  add constraint company_feedback_type_check
  check (feedback_type in ('like', 'dislike'));

create index if not exists idx_company_feedback_user_created
  on company_feedback (user_id, created_at desc);
create index if not exists idx_company_feedback_company
  on company_feedback (company_id);

-- -----------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------
alter table orchestration_state enable row level security;
alter table user_companies enable row level security;
alter table company_feedback enable row level security;

create policy "Service role can do everything on orchestration_state" on orchestration_state
  for all using (true) with check (true);

create policy "Service role can do everything on user_companies" on user_companies
  for all using (true) with check (true);

create policy "Service role can do everything on company_feedback" on company_feedback
  for all using (true) with check (true);

-- Optional user-auth policies (work if JWT user id is available)
create policy "Users can read own orchestration_state" on orchestration_state
  for select using (auth.uid()::text = user_id);
create policy "Users can update own orchestration_state" on orchestration_state
  for update using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
create policy "Users can read own user_companies" on user_companies
  for select using (auth.uid()::text = user_id);
create policy "Users can write own user_companies" on user_companies
  for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
create policy "Users can read own company_feedback" on company_feedback
  for select using (auth.uid()::text = user_id);
create policy "Users can write own company_feedback" on company_feedback
  for all using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);

-- Reuse updated_at trigger if created in 001
create trigger orchestration_state_updated_at
  before update on orchestration_state
  for each row execute function update_updated_at();

create trigger user_companies_updated_at
  before update on user_companies
  for each row execute function update_updated_at();

create trigger company_feedback_updated_at
  before update on company_feedback
  for each row execute function update_updated_at();
