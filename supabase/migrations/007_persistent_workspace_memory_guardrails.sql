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
