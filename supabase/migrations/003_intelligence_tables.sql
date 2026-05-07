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
