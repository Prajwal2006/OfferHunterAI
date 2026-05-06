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
