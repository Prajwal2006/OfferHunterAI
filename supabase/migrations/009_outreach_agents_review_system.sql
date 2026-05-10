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
