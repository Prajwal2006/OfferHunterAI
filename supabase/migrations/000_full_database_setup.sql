-- OfferHunter AI - Consolidated Supabase migration
-- Generated from 001..009 migration files
-- Run this file once on a fresh Supabase database


-- ==================================================================
-- BEGIN FILE: 001_initial_schema.sql
-- ==================================================================

-- OfferHunter AI — Initial Database Schema
-- Run this in the Supabase SQL editor

-- Enable required extensions
create extension if not exists "uuid-ossp";

-- ─── Agent Events ─────────────────────────────────────────────────────────────
create table if not exists agent_events (
  id          uuid primary key default uuid_generate_v4(),
  agent_name  text not null,
  task_id     text not null,
  status      text not null check (status in ('started', 'running', 'completed', 'failed')),
  message     text not null,
  metadata    jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists idx_agent_events_agent_name on agent_events (agent_name);
create index if not exists idx_agent_events_task_id on agent_events (task_id);
create index if not exists idx_agent_events_created_at on agent_events (created_at desc);

-- Enable realtime for agent_events
alter publication supabase_realtime add table agent_events;

-- ─── Companies ────────────────────────────────────────────────────────────────
create table if not exists companies (
  id               uuid primary key default uuid_generate_v4(),
  name             text not null,
  domain           text not null,
  industry         text,
  size             text,
  relevance_score  float not null default 0.0,
  status           text not null default 'discovered'
                     check (status in ('discovered', 'personalized', 'email_drafted',
                                       'pending_approval', 'sent', 'replied', 'followed_up')),
  metadata         jsonb not null default '{}',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_companies_status on companies (status);
create index if not exists idx_companies_relevance on companies (relevance_score desc);

-- ─── Emails ───────────────────────────────────────────────────────────────────
create table if not exists emails (
  id               uuid primary key default uuid_generate_v4(),
  company_id       uuid references companies (id) on delete cascade,
  company_name     text not null,
  subject          text not null,
  body             text not null,
  recipient_email  text,
  status           text not null default 'pending_approval'
                     check (status in ('pending_approval', 'approved', 'rejected', 'sent', 'failed')),
  sent_at          timestamptz,
  gmail_message_id text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_emails_status on emails (status);
create index if not exists idx_emails_company_id on emails (company_id);

-- ─── Follow-ups ───────────────────────────────────────────────────────────────
create table if not exists follow_ups (
  id              uuid primary key default uuid_generate_v4(),
  email_id        uuid references emails (id) on delete cascade,
  follow_up_number int not null default 1,
  body            text not null,
  status          text not null default 'pending_approval'
                    check (status in ('pending_approval', 'approved', 'sent', 'skipped')),
  scheduled_at    timestamptz not null,
  sent_at         timestamptz,
  created_at      timestamptz not null default now()
);

-- ─── Pipeline view ────────────────────────────────────────────────────────────
create or replace view pipeline as
  select
    c.id,
    c.name,
    c.domain,
    c.industry,
    c.size,
    c.relevance_score,
    c.status,
    c.created_at,
    (
      select jsonb_agg(e.* order by e.created_at)
      from emails e
      where e.company_id = c.id
    ) as emails
  from companies c
  order by c.created_at desc;

-- ─── Row Level Security ───────────────────────────────────────────────────────
alter table agent_events enable row level security;
alter table companies enable row level security;
alter table emails enable row level security;
alter table follow_ups enable row level security;

-- Allow service role to do everything
create policy "Service role can do everything" on agent_events
  for all using (true) with check (true);
create policy "Service role can do everything" on companies
  for all using (true) with check (true);
create policy "Service role can do everything" on emails
  for all using (true) with check (true);
create policy "Service role can do everything" on follow_ups
  for all using (true) with check (true);

-- Allow anonymous reads for dashboard
create policy "Anon can read agent_events" on agent_events
  for select using (true);
create policy "Anon can read companies" on companies
  for select using (true);
create policy "Anon can read emails" on emails
  for select using (true);

-- ─── Triggers for updated_at ──────────────────────────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger companies_updated_at
  before update on companies
  for each row execute function update_updated_at();

create trigger emails_updated_at
  before update on emails
  for each row execute function update_updated_at();

-- END FILE: 001_initial_schema.sql


-- ==================================================================
-- BEGIN FILE: 002_resume_versions.sql
-- ==================================================================

-- OfferHunter AI — Resume versions and email resume linkage

create table if not exists resume_versions (
  id               uuid primary key default uuid_generate_v4(),
  user_id          text not null,
  file_name        text not null,
  version_label    text not null,
  extracted_text   text not null,
  extracted_skills jsonb not null default '[]'::jsonb,
  is_active        boolean not null default false,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_resume_versions_user_id on resume_versions (user_id);
create index if not exists idx_resume_versions_active on resume_versions (user_id, is_active);

alter table emails add column if not exists resume_version_id uuid references resume_versions (id) on delete set null;
alter table emails add column if not exists resume_skills jsonb not null default '[]'::jsonb;
alter table emails add column if not exists resume_excerpt text;

alter table resume_versions enable row level security;

create policy "Service role can do everything on resume_versions" on resume_versions
  for all using (true) with check (true);

create trigger resume_versions_updated_at
  before update on resume_versions
  for each row execute function update_updated_at();

-- END FILE: 002_resume_versions.sql


-- ==================================================================
-- BEGIN FILE: 003_company_finder_schema.sql
-- ==================================================================

-- OfferHunter AI — Company Finder Agent Schema
-- Migration 003: Full Company Finder data model

-- ─── Parsed Resume Profiles ───────────────────────────────────────────────────
create table if not exists parsed_profiles (
  id                uuid primary key default uuid_generate_v4(),
  user_id           text not null unique,
  resume_id         uuid references resume_versions (id) on delete set null,
  full_name         text,
  email             text,
  phone             text,
  location          text,
  citizenship       text,
  education         jsonb not null default '[]',
  gpa               text,
  skills            jsonb not null default '[]',
  tech_stack        jsonb not null default '[]',
  certifications    jsonb not null default '[]',
  work_experience   jsonb not null default '[]',
  projects          jsonb not null default '[]',
  leadership        jsonb not null default '[]',
  research          jsonb not null default '[]',
  awards            jsonb not null default '[]',
  preferred_domains jsonb not null default '[]',
  keywords          jsonb not null default '[]',
  linkedin_url      text,
  github_url        text,
  portfolio_url     text,
  other_links       jsonb not null default '[]',
  raw_text          text,
  parse_version     int not null default 1,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_parsed_profiles_user_id on parsed_profiles (user_id);

-- ─── User Preferences ─────────────────────────────────────────────────────────
create table if not exists user_preferences (
  id                      uuid primary key default uuid_generate_v4(),
  user_id                 text not null unique,
  preferred_roles         jsonb not null default '[]',
  preferred_locations     jsonb not null default '[]',
  open_to_relocation      boolean,
  work_mode               text check (work_mode in ('remote', 'hybrid', 'onsite', 'flexible')),
  employment_type         jsonb not null default '[]',
  salary_min              int,
  salary_max              int,
  open_to_startups        boolean,
  company_size_pref       jsonb not null default '[]',
  industries_of_interest  jsonb not null default '[]',
  sponsorship_required    boolean,
  work_authorization      text,
  graduation_date         text,
  earliest_start          text,
  preferred_tech_stack    jsonb not null default '[]',
  career_priorities       jsonb not null default '{}',
  avoided_companies       jsonb not null default '[]',
  avoided_industries      jsonb not null default '[]',
  open_to_cold_outreach   boolean not null default true,
  profile_links           jsonb not null default '{}',
  conversation_complete   boolean not null default false,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create index if not exists idx_user_preferences_user_id on user_preferences (user_id);

-- ─── Enhance Companies Table ──────────────────────────────────────────────────
alter table companies
  add column if not exists user_id            text,
  add column if not exists logo_url           text,
  add column if not exists description        text,
  add column if not exists mission            text,
  add column if not exists tech_stack         jsonb not null default '[]',
  add column if not exists funding_stage      text,
  add column if not exists founded_year       int,
  add column if not exists hiring_status      text not null default 'unknown'
                             check (hiring_status in ('actively_hiring', 'hiring', 'unknown', 'not_hiring')),
  add column if not exists sponsorship_available boolean,
  add column if not exists remote_friendly    boolean,
  add column if not exists open_positions     jsonb not null default '[]',
  add column if not exists recent_news        jsonb not null default '[]',
  add column if not exists culture_tags       jsonb not null default '[]',
  add column if not exists headquarters       text,
  add column if not exists website_url        text,
  add column if not exists linkedin_url       text,
  add column if not exists glassdoor_url      text,
  add column if not exists crunchbase_url     text,
  add column if not exists source             text,
  add column if not exists source_url         text,
  add column if not exists last_scraped_at    timestamptz;

-- ─── Company Contacts ─────────────────────────────────────────────────────────
create table if not exists company_contacts (
  id           uuid primary key default uuid_generate_v4(),
  company_id   uuid references companies (id) on delete cascade,
  name         text,
  title        text,
  email        text,
  linkedin_url text,
  contact_type text check (contact_type in ('recruiter', 'founder', 'hiring_manager', 'engineer', 'hr', 'other')),
  confidence   float not null default 0.0,
  verified     boolean not null default false,
  source       text,
  created_at   timestamptz not null default now()
);

create index if not exists idx_company_contacts_company_id on company_contacts (company_id);

-- ─── Company Rankings (per user) ──────────────────────────────────────────────
create table if not exists company_rankings (
  id                  uuid primary key default uuid_generate_v4(),
  user_id             text not null,
  company_id          uuid references companies (id) on delete cascade,
  match_score         float not null default 0.0,
  resume_match        float not null default 0.0,
  skills_match        float not null default 0.0,
  interests_match     float not null default 0.0,
  location_match      float not null default 0.0,
  compensation_match  float not null default 0.0,
  tech_stack_match    float not null default 0.0,
  visa_compatibility  float not null default 0.0,
  hiring_likelihood   float not null default 0.0,
  match_explanation   text,
  strengths           jsonb not null default '[]',
  gaps                jsonb not null default '[]',
  suggestions         jsonb not null default '[]',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (user_id, company_id)
);

create index if not exists idx_company_rankings_user_id on company_rankings (user_id);
create index if not exists idx_company_rankings_score   on company_rankings (user_id, match_score desc);

-- ─── Discovered Jobs ──────────────────────────────────────────────────────────
create table if not exists discovered_jobs (
  id              uuid primary key default uuid_generate_v4(),
  company_id      uuid references companies (id) on delete cascade,
  title           text not null,
  url             text,
  location        text,
  work_mode       text,
  employment_type text,
  salary_range    text,
  posted_at       text,
  description     text,
  requirements    jsonb not null default '[]',
  created_at      timestamptz not null default now()
);

create index if not exists idx_discovered_jobs_company_id on discovered_jobs (company_id);

-- ─── AI Agent Runs ────────────────────────────────────────────────────────────
create table if not exists ai_agent_runs (
  id           uuid primary key default uuid_generate_v4(),
  user_id      text not null,
  agent_name   text not null,
  task_id      text not null,
  status       text not null check (status in ('started', 'running', 'completed', 'failed')),
  input        jsonb not null default '{}',
  output       jsonb not null default '{}',
  error        text,
  started_at   timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists idx_ai_agent_runs_user_id    on ai_agent_runs (user_id);
create index if not exists idx_ai_agent_runs_task_id    on ai_agent_runs (task_id);
create index if not exists idx_ai_agent_runs_agent_name on ai_agent_runs (agent_name);

-- ─── Conversation History (for preference collector) ──────────────────────────
create table if not exists conversation_history (
  id         uuid primary key default uuid_generate_v4(),
  user_id    text not null,
  context    text not null default 'preferences',
  role       text not null check (role in ('user', 'assistant', 'system')),
  content    text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_conversation_history_user_id on conversation_history (user_id, context, created_at);

-- ─── RLS Policies ─────────────────────────────────────────────────────────────
alter table parsed_profiles     enable row level security;
alter table user_preferences    enable row level security;
alter table company_contacts    enable row level security;
alter table company_rankings    enable row level security;
alter table discovered_jobs     enable row level security;
alter table ai_agent_runs       enable row level security;
alter table conversation_history enable row level security;

-- Service role bypass policies
create policy "Service role full access on parsed_profiles"
  on parsed_profiles for all using (true) with check (true);

create policy "Service role full access on user_preferences"
  on user_preferences for all using (true) with check (true);

create policy "Service role full access on company_contacts"
  on company_contacts for all using (true) with check (true);

create policy "Service role full access on company_rankings"
  on company_rankings for all using (true) with check (true);

create policy "Service role full access on discovered_jobs"
  on discovered_jobs for all using (true) with check (true);

create policy "Service role full access on ai_agent_runs"
  on ai_agent_runs for all using (true) with check (true);

create policy "Service role full access on conversation_history"
  on conversation_history for all using (true) with check (true);

-- ─── Updated At Triggers ──────────────────────────────────────────────────────
create trigger parsed_profiles_updated_at
  before update on parsed_profiles
  for each row execute function update_updated_at();

create trigger user_preferences_updated_at
  before update on user_preferences
  for each row execute function update_updated_at();

create trigger company_rankings_updated_at
  before update on company_rankings
  for each row execute function update_updated_at();

-- END FILE: 003_company_finder_schema.sql


-- ==================================================================
-- BEGIN FILE: 003_intelligence_tables.sql
-- ==================================================================

-- ============================================================
-- 003_intelligence_tables.sql
-- Adds discovery session tracking, semantic embeddings, company
-- enrichment metadata, and discovery analytics.
-- ============================================================

-- Enable pgvector for semantic similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Discovery sessions ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS discovery_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    queries_used    JSONB NOT NULL DEFAULT '[]',
    sources_searched JSONB NOT NULL DEFAULT '[]',
    companies_found INTEGER NOT NULL DEFAULT 0,
    feedback_rounds INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_sessions_user_id
    ON discovery_sessions (user_id);

-- ── Company semantic embeddings ─────────────────────────────
CREATE TABLE IF NOT EXISTS company_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID REFERENCES companies(id) ON DELETE CASCADE,
    domain      TEXT NOT NULL UNIQUE,
    embedding   vector(1536),
    model       TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_embeddings_domain
    ON company_embeddings (domain);

-- ── Company enrichment metadata ─────────────────────────────
CREATE TABLE IF NOT EXISTS enrichment_data (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id           UUID REFERENCES companies(id) ON DELETE CASCADE,
    domain               TEXT NOT NULL UNIQUE,
    github_org           TEXT,
    github_stars         INTEGER,
    github_repos         INTEGER,
    growth_signals       JSONB NOT NULL DEFAULT '[]',
    hiring_signal_count  INTEGER NOT NULL DEFAULT 0,
    engineering_role_count INTEGER NOT NULL DEFAULT 0,
    ai_adoption          BOOLEAN NOT NULL DEFAULT FALSE,
    remote_confidence    FLOAT,
    enrichment_version   INTEGER NOT NULL DEFAULT 1,
    enriched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_data_domain
    ON enrichment_data (domain);

-- ── Discovery analytics ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS discovery_analytics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT NOT NULL,
    company_id          UUID REFERENCES companies(id),
    source              TEXT,
    discovery_queries   JSONB NOT NULL DEFAULT '[]',
    semantic_similarity FLOAT,
    ranking_signals     JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_analytics_user_id
    ON discovery_analytics (user_id);
CREATE INDEX IF NOT EXISTS idx_discovery_analytics_company_id
    ON discovery_analytics (company_id);

-- END FILE: 003_intelligence_tables.sql


-- ==================================================================
-- BEGIN FILE: 004_persistent_company_workspace.sql
-- ==================================================================

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

-- END FILE: 004_persistent_company_workspace.sql


-- ==================================================================
-- BEGIN FILE: 005_fix_company_unique_domain.sql
-- ==================================================================

-- ============================================================
-- 005_fix_company_unique_domain.sql
-- Add UNIQUE(domain) constraint to companies so that
-- upsert(on_conflict="domain") works correctly.
-- Also ensures RLS policies permit the service role to write.
-- ============================================================

-- Step 1: De-duplicate existing rows keeping the newest per domain
--         (by highest ctid if created_at is tied).
DELETE FROM companies a
  USING companies b
  WHERE a.domain = b.domain
    AND a.ctid < b.ctid;

-- Step 2: Add the unique constraint (idempotent)
ALTER TABLE companies
  ADD CONSTRAINT companies_domain_unique UNIQUE (domain);

-- Step 3: Ensure the user_companies table exists (in case migration 004
--         was not applied yet in this environment).
CREATE TABLE IF NOT EXISTS user_companies (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id text NOT NULL,
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  discovery_session_id uuid REFERENCES discovery_sessions(id) ON DELETE SET NULL,
  source text,
  discovered_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'active',
  orchestration_stage text NOT NULL DEFAULT 'CompanyFinder',
  liked boolean,
  disliked boolean,
  archived boolean NOT NULL DEFAULT false,
  removed boolean NOT NULL DEFAULT false,
  manually_added boolean NOT NULL DEFAULT false,
  personalization_completed boolean NOT NULL DEFAULT false,
  outreach_started boolean NOT NULL DEFAULT false,
  outreach_sent boolean NOT NULL DEFAULT false,
  notes text,
  ranking_score float,
  ranking_explanation text,
  ranking_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  application_strategy text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_user_companies_user_updated
  ON user_companies (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_companies_user_flags
  ON user_companies (user_id, archived, removed);
CREATE INDEX IF NOT EXISTS idx_user_companies_user_score
  ON user_companies (user_id, ranking_score DESC NULLS LAST);

-- Step 4: If user_companies is empty but company_rankings has data,
--         backfill user_companies from company_rankings so existing
--         discovered companies immediately appear.
INSERT INTO user_companies (
  user_id, company_id, source, status, orchestration_stage,
  ranking_score, ranking_explanation, ranking_metadata
)
SELECT
  cr.user_id,
  cr.company_id,
  COALESCE(c.source, 'legacy') AS source,
  'active' AS status,
  'Personalization' AS orchestration_stage,
  cr.match_score AS ranking_score,
  COALESCE(cr.match_explanation, '') AS ranking_explanation,
  jsonb_build_object(
    'match_score', cr.match_score,
    'resume_match', cr.resume_match,
    'skills_match', cr.skills_match,
    'interests_match', cr.interests_match,
    'location_match', cr.location_match,
    'match_explanation', cr.match_explanation
  ) AS ranking_metadata
FROM company_rankings cr
JOIN companies c ON c.id = cr.company_id
WHERE NOT EXISTS (
  SELECT 1 FROM user_companies uc
  WHERE uc.user_id = cr.user_id
    AND uc.company_id = cr.company_id
);

-- Step 5: Ensure orchestration_state table exists
CREATE TABLE IF NOT EXISTS orchestration_state (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id text NOT NULL UNIQUE,
  current_stage text NOT NULL DEFAULT 'CompanyFinder',
  progress jsonb NOT NULL DEFAULT '{}'::jsonb,
  active_agents jsonb NOT NULL DEFAULT '[]'::jsonb,
  paused_state boolean NOT NULL DEFAULT false,
  last_task_id text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Step 6: Enable RLS (service role bypasses it, but needed for frontend direct access)
ALTER TABLE user_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE orchestration_state ENABLE ROW LEVEL SECURITY;

-- Policies (service role always bypasses RLS, these are for anon/authenticated)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_companies' AND policyname = 'user_companies_select_own'
  ) THEN
    CREATE POLICY user_companies_select_own ON user_companies
      FOR SELECT USING (auth.uid()::text = user_id);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'user_companies' AND policyname = 'user_companies_all_own'
  ) THEN
    CREATE POLICY user_companies_all_own ON user_companies
      FOR ALL USING (auth.uid()::text = user_id);
  END IF;
END $$;

-- END FILE: 005_fix_company_unique_domain.sql


-- ==================================================================
-- BEGIN FILE: 006_discovery_source_logs.sql
-- ==================================================================

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

-- END FILE: 006_discovery_source_logs.sql


-- ==================================================================
-- BEGIN FILE: 007_persistent_workspace_memory_guardrails.sql
-- ==================================================================

-- ============================================================
-- 007_persistent_workspace_memory_guardrails.sql
-- Make Company Finder a durable append-only opportunity workspace.
-- ============================================================

create extension if not exists "uuid-ossp";

-- Ensure persistent workspace columns exist even in partially migrated DBs.
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

alter table user_companies
  add column if not exists discovery_session_id uuid references discovery_sessions(id) on delete set null,
  add column if not exists source text,
  add column if not exists discovered_at timestamptz not null default now(),
  add column if not exists status text not null default 'active',
  add column if not exists orchestration_stage text not null default 'CompanyFinder',
  add column if not exists liked boolean,
  add column if not exists disliked boolean,
  add column if not exists archived boolean not null default false,
  add column if not exists removed boolean not null default false,
  add column if not exists manually_added boolean not null default false,
  add column if not exists personalization_completed boolean not null default false,
  add column if not exists outreach_started boolean not null default false,
  add column if not exists outreach_sent boolean not null default false,
  add column if not exists notes text,
  add column if not exists ranking_score float,
  add column if not exists ranking_explanation text,
  add column if not exists ranking_metadata jsonb not null default '{}'::jsonb,
  add column if not exists application_strategy text,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists idx_user_companies_unique_user_company
  on user_companies (user_id, company_id);
create index if not exists idx_user_companies_user_active_updated
  on user_companies (user_id, archived, removed, updated_at desc);
create index if not exists idx_user_companies_user_stage
  on user_companies (user_id, orchestration_stage);
create index if not exists idx_user_companies_user_score
  on user_companies (user_id, ranking_score desc nulls last);

-- Recover legacy discoveries that were ranked but never attached to the
-- persistent workspace. This is intentionally insert-only.
insert into user_companies (
  user_id,
  company_id,
  source,
  status,
  orchestration_stage,
  ranking_score,
  ranking_explanation,
  ranking_metadata,
  metadata
)
select
  cr.user_id,
  cr.company_id,
  coalesce(c.source, 'legacy') as source,
  'active' as status,
  'Personalization' as orchestration_stage,
  cr.match_score as ranking_score,
  coalesce(cr.match_explanation, '') as ranking_explanation,
  jsonb_strip_nulls(jsonb_build_object(
    'match_score', cr.match_score,
    'resume_match', cr.resume_match,
    'skills_match', cr.skills_match,
    'interests_match', cr.interests_match,
    'location_match', cr.location_match,
    'compensation_match', cr.compensation_match,
    'tech_stack_match', cr.tech_stack_match,
    'visa_compatibility', cr.visa_compatibility,
    'hiring_likelihood', cr.hiring_likelihood,
    'match_explanation', cr.match_explanation,
    'strengths', cr.strengths,
    'gaps', cr.gaps,
    'suggestions', cr.suggestions
  )) as ranking_metadata,
  jsonb_build_object('backfilled_from', 'company_rankings', 'domain', c.domain) as metadata
from company_rankings cr
join companies c on c.id = cr.company_id
where not exists (
  select 1
  from user_companies uc
  where uc.user_id = cr.user_id
    and uc.company_id = cr.company_id
);

-- Recover rows from the older model where companies.user_id carried ownership
-- directly and no user_companies row was created.
insert into user_companies (
  user_id,
  company_id,
  source,
  status,
  orchestration_stage,
  ranking_score,
  ranking_metadata,
  metadata
)
select
  c.user_id,
  c.id,
  coalesce(c.source, 'legacy') as source,
  'active' as status,
  'Personalization' as orchestration_stage,
  c.relevance_score as ranking_score,
  jsonb_build_object(
    'match_score', c.relevance_score,
    'signal_source', 'legacy_companies_user_id'
  ) as ranking_metadata,
  jsonb_build_object('backfilled_from', 'companies.user_id', 'domain', c.domain) as metadata
from companies c
where c.user_id is not null
  and not exists (
    select 1
    from user_companies uc
    where uc.user_id = c.user_id
      and uc.company_id = c.id
  );

-- Keep orchestration memory present for users with workspace companies.
insert into orchestration_state (
  user_id,
  current_stage,
  active_agents,
  paused_state,
  progress
)
select
  uc.user_id,
  'Personalization',
  '[]'::jsonb,
  false,
  jsonb_build_object(
    'step', 'persistent_workspace_restored',
    'companies_found', count(*)
  )
from user_companies uc
where not exists (
  select 1 from orchestration_state os where os.user_id = uc.user_id
)
group by uc.user_id;

alter table user_companies enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'user_companies'
      and policyname = 'user_companies_service_role_all'
  ) then
    create policy user_companies_service_role_all on user_companies
      for all using (true) with check (true);
  end if;
end $$;

-- END FILE: 007_persistent_workspace_memory_guardrails.sql


-- ==================================================================
-- BEGIN FILE: 008_safe_company_domain_consolidation.sql
-- ==================================================================

-- ============================================================
-- 008_safe_company_domain_consolidation.sql
-- Preserve workspace links when consolidating duplicate company domains.
-- ============================================================

-- Migration 005 used a direct DELETE to deduplicate companies by domain. With
-- ON DELETE CASCADE references, that can remove user_companies/company_rankings
-- rows for the deleted duplicate. This migration performs future consolidation
-- by moving child references to the survivor before deleting duplicate rows.

create temporary table if not exists company_domain_survivors as
select
  lower(domain) as domain_key,
  max(id::text)::uuid as survivor_id
from companies
where domain is not null and trim(domain) <> ''
group by lower(domain)
having count(*) > 1;

update user_companies uc
set company_id = s.survivor_id
from companies c
join company_domain_survivors s on lower(c.domain) = s.domain_key
where uc.company_id = c.id
  and c.id <> s.survivor_id
  and not exists (
    select 1
    from user_companies existing
    where existing.user_id = uc.user_id
      and existing.company_id = s.survivor_id
  );

delete from user_companies uc
using companies c, company_domain_survivors s
where uc.company_id = c.id
  and lower(c.domain) = s.domain_key
  and c.id <> s.survivor_id;

update company_rankings cr
set company_id = s.survivor_id
from companies c
join company_domain_survivors s on lower(c.domain) = s.domain_key
where cr.company_id = c.id
  and c.id <> s.survivor_id
  and not exists (
    select 1
    from company_rankings existing
    where existing.user_id = cr.user_id
      and existing.company_id = s.survivor_id
  );

delete from company_rankings cr
using companies c, company_domain_survivors s
where cr.company_id = c.id
  and lower(c.domain) = s.domain_key
  and c.id <> s.survivor_id;

update company_contacts cc
set company_id = s.survivor_id
from companies c
join company_domain_survivors s on lower(c.domain) = s.domain_key
where cc.company_id = c.id
  and c.id <> s.survivor_id;

update discovered_jobs dj
set company_id = s.survivor_id
from companies c
join company_domain_survivors s on lower(c.domain) = s.domain_key
where dj.company_id = c.id
  and c.id <> s.survivor_id;

update emails e
set company_id = s.survivor_id
from companies c
join company_domain_survivors s on lower(c.domain) = s.domain_key
where e.company_id = c.id
  and c.id <> s.survivor_id;

delete from companies c
using company_domain_survivors s
where lower(c.domain) = s.domain_key
  and c.id <> s.survivor_id;

drop table if exists company_domain_survivors;

-- END FILE: 008_safe_company_domain_consolidation.sql


-- ==================================================================
-- BEGIN FILE: 009_outreach_agents_review_system.sql
-- ==================================================================

-- OfferHunter AI - Outreach agents, human review, and immutable versioning

create extension if not exists "uuid-ossp";

create table if not exists personalization_profiles (
  id                         uuid primary key default uuid_generate_v4(),
  user_id                    text not null,
  company_id                 uuid not null references companies (id) on delete cascade,
  fit_score                  int not null default 0 check (fit_score between 0 and 100),
  outreach_type              text not null default 'cold_email',
  tone                       text not null default 'professional_concise',
  company_alignment          jsonb not null default '[]',
  relevant_projects          jsonb not null default '[]',
  relevant_skills            jsonb not null default '[]',
  suggested_links            jsonb not null default '[]',
  recommended_hooks          jsonb not null default '[]',
  email_strategy             jsonb not null default '{}',
  key_points_to_mention      jsonb not null default '[]',
  personalization_summary    text not null default '',
  evidence                   jsonb not null default '{}',
  created_at                 timestamptz not null default now(),
  updated_at                 timestamptz not null default now(),
  unique (user_id, company_id)
);

create index if not exists idx_personalization_profiles_user_company
  on personalization_profiles (user_id, company_id);
create index if not exists idx_personalization_profiles_fit
  on personalization_profiles (user_id, fit_score desc);

create table if not exists outreach_contacts (
  id              uuid primary key default uuid_generate_v4(),
  user_id         text not null,
  company_id      uuid not null references companies (id) on delete cascade,
  name            text not null default '',
  role            text not null default '',
  title           text not null default '',
  email           text not null,
  confidence      float not null default 0,
  source          text not null default '',
  priority_score  int not null default 0 check (priority_score between 0 and 100),
  verified        boolean not null default false,
  contact_type    text not null default 'other'
                    check (contact_type in ('recruiter', 'founder', 'hiring_manager', 'engineer', 'hr', 'other')),
  metadata        jsonb not null default '{}',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (user_id, company_id, email)
);

create index if not exists idx_outreach_contacts_user_company
  on outreach_contacts (user_id, company_id, priority_score desc);

create table if not exists email_drafts (
  id                    uuid primary key default uuid_generate_v4(),
  user_id               text not null,
  company_id            uuid not null references companies (id) on delete cascade,
  company_name          text not null,
  outreach_type         text not null default 'cold_email',
  tone                  text not null default 'professional_concise',
  selected_variant      text not null default 'medium',
  subject               text not null default '',
  body                  text not null default '',
  variants              jsonb not null default '{}',
  subjects              jsonb not null default '[]',
  recipient_email       text,
  status                text not null default 'pending_approval'
                          check (status in ('draft', 'pending_approval', 'approved', 'rejected', 'scheduled', 'sent', 'failed')),
  version_number        int not null default 1,
  resume_version_id     uuid references resume_versions (id) on delete set null,
  resume_skills         jsonb not null default '[]',
  generation_metadata   jsonb not null default '{}',
  scheduled_at          timestamptz,
  sent_at               timestamptz,
  send_provider         text,
  provider_message_id   text,
  tracking_metadata     jsonb not null default '{}',
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  last_edited_at        timestamptz not null default now(),
  unique (user_id, company_id)
);

create index if not exists idx_email_drafts_user_status
  on email_drafts (user_id, status, last_edited_at desc);
create index if not exists idx_email_drafts_company
  on email_drafts (company_id);

create table if not exists email_versions (
  id                uuid primary key default uuid_generate_v4(),
  draft_id          uuid not null references email_drafts (id) on delete cascade,
  user_id           text not null,
  company_id        uuid not null references companies (id) on delete cascade,
  version_number    int not null,
  subject           text not null default '',
  body              text not null default '',
  selected_variant  text not null default 'medium',
  recipient_email   text,
  snapshot          jsonb not null default '{}',
  event_type        text not null default 'manual_edit',
  editor            text not null default 'user' check (editor in ('user', 'ai', 'system')),
  changes           jsonb not null default '{}',
  created_at        timestamptz not null default now(),
  unique (draft_id, version_number)
);

create index if not exists idx_email_versions_draft
  on email_versions (draft_id, version_number desc);

create table if not exists generated_subjects (
  id          uuid primary key default uuid_generate_v4(),
  draft_id    uuid not null references email_drafts (id) on delete cascade,
  label       text not null default '',
  subject     text not null,
  selected    boolean not null default false,
  metadata    jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists idx_generated_subjects_draft on generated_subjects (draft_id);

create table if not exists ai_edit_requests (
  id             uuid primary key default uuid_generate_v4(),
  draft_id       uuid not null references email_drafts (id) on delete cascade,
  user_id        text not null,
  instruction    text not null,
  selected_text  text not null default '',
  proposed_text  text,
  diff           text,
  status         text not null default 'previewed'
                   check (status in ('previewed', 'accepted', 'rejected', 'failed')),
  metadata       jsonb not null default '{}',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists idx_ai_edit_requests_draft on ai_edit_requests (draft_id, created_at desc);

create table if not exists edit_history (
  id          uuid primary key default uuid_generate_v4(),
  draft_id    uuid not null references email_drafts (id) on delete cascade,
  user_id     text not null,
  edit_type   text not null default 'manual',
  before      jsonb not null default '{}',
  after       jsonb not null default '{}',
  metadata    jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists idx_edit_history_draft on edit_history (draft_id, created_at desc);

alter table emails
  add column if not exists resume_version_id uuid references resume_versions (id) on delete set null,
  add column if not exists resume_skills jsonb not null default '[]';

alter table personalization_profiles enable row level security;
alter table outreach_contacts enable row level security;
alter table email_drafts enable row level security;
alter table email_versions enable row level security;
alter table generated_subjects enable row level security;
alter table ai_edit_requests enable row level security;
alter table edit_history enable row level security;

create policy "Service role full access on personalization_profiles"
  on personalization_profiles for all using (true) with check (true);
create policy "Service role full access on outreach_contacts"
  on outreach_contacts for all using (true) with check (true);
create policy "Service role full access on email_drafts"
  on email_drafts for all using (true) with check (true);
create policy "Service role full access on email_versions"
  on email_versions for all using (true) with check (true);
create policy "Service role full access on generated_subjects"
  on generated_subjects for all using (true) with check (true);
create policy "Service role full access on ai_edit_requests"
  on ai_edit_requests for all using (true) with check (true);
create policy "Service role full access on edit_history"
  on edit_history for all using (true) with check (true);

create trigger personalization_profiles_updated_at
  before update on personalization_profiles
  for each row execute function update_updated_at();
create trigger outreach_contacts_updated_at
  before update on outreach_contacts
  for each row execute function update_updated_at();
create trigger email_drafts_updated_at
  before update on email_drafts
  for each row execute function update_updated_at();
create trigger ai_edit_requests_updated_at
  before update on ai_edit_requests
  for each row execute function update_updated_at();

-- END FILE: 009_outreach_agents_review_system.sql

