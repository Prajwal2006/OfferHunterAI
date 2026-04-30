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
