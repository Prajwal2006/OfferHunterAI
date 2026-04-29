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
