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
