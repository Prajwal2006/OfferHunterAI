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
