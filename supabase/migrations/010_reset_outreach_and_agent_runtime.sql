-- OfferHunter AI - Reset outreach and agent runtime tables for single-email AI generation

create extension if not exists "uuid-ossp";

begin;

drop table if exists email_generation_attempts cascade;
drop table if exists ai_edit_requests cascade;
drop table if exists edit_history cascade;
drop table if exists generated_subjects cascade;
drop table if exists email_versions cascade;
drop table if exists email_drafts cascade;
drop table if exists outreach_contacts cascade;
drop table if exists personalization_profiles cascade;
drop table if exists agent_events cascade;

create table agent_events (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  agent_name text not null,
  task_id text not null,
  status text not null check (status in ('started', 'running', 'completed', 'failed')),
  message text not null,
  metadata jsonb not null default '{}',
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create index idx_agent_events_user_created
  on agent_events (user_id, created_at desc);

create index idx_agent_events_active
  on agent_events (user_id, status, expires_at)
  where status in ('started', 'running');

do $$
begin
  alter publication supabase_realtime add table agent_events;
exception
  when duplicate_object then null;
  when undefined_object then null;
end $$;

create table personalization_profiles (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  company_id uuid not null references companies (id) on delete cascade,
  fit_score int not null default 0 check (fit_score between 0 and 100),
  outreach_type text not null default 'cold_email',
  tone text not null default 'professional_concise',
  company_alignment jsonb not null default '[]',
  relevant_projects jsonb not null default '[]',
  relevant_skills jsonb not null default '[]',
  suggested_links jsonb not null default '[]',
  recommended_hooks jsonb not null default '[]',
  email_strategy jsonb not null default '{}',
  key_points_to_mention jsonb not null default '[]',
  personalization_summary text not null default '',
  evidence jsonb not null default '{}',
  generated_by text not null default 'openai' check (generated_by in ('openai', 'deterministic')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, company_id)
);

create table outreach_contacts (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  company_id uuid not null references companies (id) on delete cascade,
  name text not null default '',
  role text not null default '',
  title text not null default '',
  email text not null,
  confidence float not null default 0,
  source text not null default '',
  priority_score int not null default 0 check (priority_score between 0 and 100),
  verified boolean not null default false,
  contact_type text not null default 'other',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, company_id, email)
);

create table email_drafts (
  id uuid primary key default uuid_generate_v4(),
  user_id text not null,
  company_id uuid not null references companies (id) on delete cascade,
  company_name text not null,
  outreach_type text not null default 'cold_email',
  tone text not null default 'professional_concise',
  subject text not null default '',
  body text not null default '',
  recipient_email text,
  status text not null default 'pending_approval'
    check (status in ('draft', 'pending_approval', 'approved', 'rejected', 'scheduled', 'sent', 'failed')),
  version_number int not null default 1,
  resume_version_id uuid references resume_versions (id) on delete set null,
  resume_skills jsonb not null default '[]',
  generation_source text not null default 'openai'
    check (generation_source in ('openai', 'default_template', 'manual')),
  generation_status text not null default 'completed'
    check (generation_status in ('pending', 'running', 'completed', 'failed', 'fallback')),
  llm_provider text,
  llm_model text,
  llm_call_id text,
  prompt_version text not null default 'email_single_v1',
  generation_error text,
  generation_context_summary jsonb not null default '{}',
  generation_metadata jsonb not null default '{}',
  scheduled_at timestamptz,
  sent_at timestamptz,
  send_provider text,
  provider_message_id text,
  tracking_metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_edited_at timestamptz not null default now(),
  unique (user_id, company_id)
);

create table email_versions (
  id uuid primary key default uuid_generate_v4(),
  draft_id uuid not null references email_drafts (id) on delete cascade,
  user_id text not null,
  company_id uuid not null references companies (id) on delete cascade,
  version_number int not null,
  subject text not null default '',
  body text not null default '',
  recipient_email text,
  snapshot jsonb not null default '{}',
  event_type text not null default 'manual_edit',
  editor text not null default 'user' check (editor in ('user', 'ai', 'system')),
  changes jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (draft_id, version_number)
);

create table email_generation_attempts (
  id uuid primary key default uuid_generate_v4(),
  draft_id uuid references email_drafts (id) on delete set null,
  user_id text not null,
  company_id uuid references companies (id) on delete cascade,
  provider text not null default 'openai',
  model text,
  status text not null check (status in ('running', 'completed', 'failed', 'fallback')),
  prompt_version text not null default 'email_single_v1',
  request_payload jsonb not null default '{}',
  context_payload jsonb not null default '{}',
  raw_response text,
  parsed_response jsonb not null default '{}',
  error text,
  tokens_prompt int,
  tokens_completion int,
  tokens_total int,
  duration_ms numeric,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table ai_edit_requests (
  id uuid primary key default uuid_generate_v4(),
  draft_id uuid not null references email_drafts (id) on delete cascade,
  user_id text not null,
  instruction text not null,
  selected_text text not null default '',
  proposed_text text,
  diff text,
  status text not null default 'previewed'
    check (status in ('previewed', 'accepted', 'rejected', 'failed')),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_personalization_profiles_user_company on personalization_profiles (user_id, company_id);
create index idx_outreach_contacts_user_company on outreach_contacts (user_id, company_id, priority_score desc);
create index idx_email_drafts_user_status on email_drafts (user_id, status, last_edited_at desc);
create index idx_email_versions_draft on email_versions (draft_id, version_number desc);
create index idx_email_generation_attempts_user_created on email_generation_attempts (user_id, created_at desc);
create index idx_ai_edit_requests_draft on ai_edit_requests (draft_id, created_at desc);

alter table agent_events enable row level security;
alter table personalization_profiles enable row level security;
alter table outreach_contacts enable row level security;
alter table email_drafts enable row level security;
alter table email_versions enable row level security;
alter table email_generation_attempts enable row level security;
alter table ai_edit_requests enable row level security;

create policy "Service role full access on agent_events" on agent_events for all using (true) with check (true);
create policy "Service role full access on personalization_profiles" on personalization_profiles for all using (true) with check (true);
create policy "Service role full access on outreach_contacts" on outreach_contacts for all using (true) with check (true);
create policy "Service role full access on email_drafts" on email_drafts for all using (true) with check (true);
create policy "Service role full access on email_versions" on email_versions for all using (true) with check (true);
create policy "Service role full access on email_generation_attempts" on email_generation_attempts for all using (true) with check (true);
create policy "Service role full access on ai_edit_requests" on ai_edit_requests for all using (true) with check (true);

commit;
