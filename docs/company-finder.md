# Company Finder Agent

The Company Finder Agent is OfferHunterAI's core intelligence layer for proactively discovering and ranking companies that match a user's resume, skills, and job preferences. It enforces hard constraints (e.g. strict remote-only) before any enrichment or persistence work happens, so only matching companies ever reach the user's workspace.

---

## High-Level Pipeline

```
POST /company-finder/run
         │
         ▼
CompanyFinderAgent.run_full_pipeline()
         │
  ┌──────┴──────────────────────────────────┐
  │  Step 1 · Resume Parse                  │
  │  ResumeParserService (GPT-4o-mini)       │
  └──────┬──────────────────────────────────┘
         │ profile: {skills, tech_stack, domains, ...}
  ┌──────┴──────────────────────────────────┐
  │  Step 2 · Feedback Learning             │
  │  Merge prior like/dislike signals into  │
  │  preferences before discovery           │
  └──────┬──────────────────────────────────┘
         │ preferences: {work_mode, roles, salary, ...}
  ┌──────┴──────────────────────────────────┐
  │  Step 3 · Discovery (incremental)       │
  │  _run_discovery_incrementally()         │
  │    → discover_stream() per-source batch │
  │    → _persist_companies() per batch     │
  └──────┬──────────────────────────────────┘
         │ persisted minimal records (no ranking yet)
  ┌──────┴──────────────────────────────────┐
  │  Step 4 · Background Hydration (async)  │
  │  asyncio.create_task(...)               │
  │    ├─ run_enrichment_worker()           │
  │    ├─ run_ranking_worker()              │
  │    ├─ run_contact_worker()              │
  │    └─ run_embedding_worker()            │
  └─────────────────────────────────────────┘
```

The pipeline returns to the caller (and emits an SSE `running` event) as soon as minimal records are persisted — background hydration completes asynchronously and each stage triggers a `refresh_companies: true` SSE event so the UI re-fetches.

---

## Step 1 — Resume Parsing

`ResumeParserService` extracts structured data from the uploaded resume text:

- **Skills & tech stack** — regex + GPT-4o-mini extraction pass
- **Work experience** — titles, companies, dates, descriptions
- **Education** — degrees, institutions
- **Inferred profile** — seniority, preferred domains, years of experience, keywords

The parsed profile is saved to `parsed_profiles` in Supabase. If already parsed, this step is skipped.

---

## Step 2 — Preference Normalization & Feedback Learning

Before discovery starts, preferences are normalized and enriched:

1. **`normalize_preference_payload(preferences)`** — canonicalises legacy `remote_only: true` into `work_mode: "remote"` so all downstream code uses a single field.
2. **Feedback learning** — `supabase_client.summarize_feedback_learning(user_id)` returns aggregated like/dislike signals from previous sessions. These are merged into preferences as soft boosts/exclusions for the AI query expander and ranker.
3. Internal `_` keys are injected: `_user_id`, `_discovery_session_id`, `_excluded_domains`, `_excluded_names`, `_discovery_round`.

---

## Step 3 — Discovery Pipeline (inside `CompanyDiscoveryService`)

`discover_stream()` runs the full multi-source pipeline and yields **per-source batches** as each source completes (streaming to `_run_discovery_incrementally()` so the UI updates incrementally).

### Phase 1 — AI Query Expansion

`QueryExpansionService.expand_queries(profile, preferences)` uses GPT-4o-mini to generate a ranked list of search strings derived from the user's skills, target roles, and industry preferences. Up to 5 queries are used per source. Falls back to a built-in heuristic set if the API call fails.

### Phase 2 — Parallel Source Execution

`SourceOrchestrator.run()` fans out to all active sources concurrently using `asyncio.gather()` with a semaphore cap of **8 concurrent sources** and a per-source timeout of **30 seconds**. Failed or timed-out sources return `[]` and a `SourceMetric` entry recording the failure reason.

**Active sources** are selected by `source_mode` (default: `"all"`):

| Mode | Active Sources |
|---|---|
| `all` | All 12 sources |
| `startups` | Greenhouse, Lever, Ashby, Workable, Crunchbase, GitHubDiscovery, HackerNews, WorkAtAStartup, Wellfound, YCombinator, AI Discovery |
| `remote` | RemoteOK, Greenhouse, Lever, Ashby, Workable, HackerNews, Wellfound |
| `yc` | YCombinator, WorkAtAStartup, Greenhouse, Lever, Ashby |
| `ai` | Greenhouse, Lever, Ashby, GitHubDiscovery, AI Discovery, HackerNews |
| `fortune500` | Greenhouse, Lever, Workable, AI Discovery, RemoteOK, HackerNews |
| `stealth` | AI Discovery, HackerNews, GitHubDiscovery |
| `international` | RemoteOK, Lever, Ashby, Workable, GitHubDiscovery, AI Discovery |
| `visa` | Greenhouse, Lever, Ashby, RemoteOK, AI Discovery, Wellfound, HackerNews |

### Phase 3 — Deduplication

Results from all sources are merged and deduplicated by normalized domain (`www.` stripped, scheme stripped). Source attribution is preserved for telemetry.

`RecursiveExpansionService` inspects the deduplicated results and generates adjacent queries from the emerging opportunity graph (e.g. if 3 fintech companies were found, it generates fintech-adjacent queries for the next round).

### Phase 4 — Feedback Loop

If fewer than 35 unique companies are found from at least 4 distinct sources, the pipeline re-runs with a widened query set for up to 3 additional rounds.

### Phase 4.5 — Industry Mismatch Filter

`_filter_industry_mismatch()` removes companies whose industry is clearly outside the user's stated industries (e.g. a manufacturing company when the user targets SaaS/AI). This is a soft heuristic, not a hard constraint.

### Phase 4.6 — Hard Constraint Enforcement ← *critical gate*

`apply_hard_constraints_with_diagnostics(companies, preferences)` runs **before any company is persisted**. It returns a `HardConstraintResult` with:

- `visible_companies` — companies that pass all hard constraints
- `hidden_companies` — companies blocked, annotated with `preference_enforcement.reasons`
- `counts_by_source` — per-source telemetry (see [Observability](#observability))

**Constraints evaluated in order:**

| Constraint | Trigger | Removal reason |
|---|---|---|
| Strict remote | `work_mode == "remote"` in preferences | Company `work_mode != "remote"` OR `remote_confidence < 0.8` |
| Job-level remote | Strict remote + company has open positions | Any job with `work_mode != "remote"` is removed from `open_positions`; if none remain, the company is hidden |
| Blocked companies | `avoided_companies` / `blocked_companies` in preferences | Company name or domain matched |
| Visa/sponsorship | `sponsorship_required: true` | Company `sponsorship_available == false` |
| Salary floor | `salary_min` set | Company max salary below user minimum |
| Excluded locations | `excluded_countries` / `excluded_locations` | Company HQ or job location matched |
| Preferred locations | `preferred_locations` set (non-remote mode) | Company HQ outside preferred list |

**Remote confidence threshold is `0.8`** — companies with `remote_confidence` between 0 and 0.8 are treated as non-remote and blocked when strict remote mode is active.

### Phase 4.7 — Workspace Deduplication

Companies already in the user's workspace (`excluded_domains`) are removed so every discovery run returns only **new** companies.

### Phase 5 — Priority Sorting

`_startup_priority_score()` sorts surviving companies by a composite of:
- Company size (startups < 200 score highest)
- Funding stage (pre-seed / seed / Series A / YC score highest)
- Source origin (Wellfound, WorkAtAStartup, HackerNews get a bonus)
- `relevance_score` (secondary tiebreaker)

---

## Work-Mode Normalization

Every company and every job within it is normalized to a canonical `WorkMode` before constraints are applied.

### `WorkMode` enum (`backend/models/work_mode.py`)

```python
class WorkMode(str, Enum):
    REMOTE  = "remote"
    HYBRID  = "hybrid"
    ONSITE  = "onsite"
    UNKNOWN = "unknown"
```

### `infer_work_mode(signals, source)` — pattern matching engine

Accepts any number of raw signals (strings, booleans, dicts, lists) and flattens them into a single lowercased text blob, then applies regex patterns in priority order:

| Priority | Pattern examples | WorkMode | Confidence |
|---|---|---|---|
| 1st | `hybrid`, `flexible hybrid`, `N days onsite` | `HYBRID` | 0.92 |
| 2nd | `onsite`, `on-site`, `in-office`, `must be based in`, `relocate to` | `ONSITE` | 0.90 |
| 3rd | `remote`, `fully remote`, `remote-first`, `work from anywhere`, `distributed team` | `REMOTE` | 0.93 |
| 4th | City/state names with no remote marker (`San Francisco`, `NY`, `CA`) | `ONSITE` | 0.72 |
| 5th | Ambiguous phrases (`flexible work environment`) | `UNKNOWN` | 0.35 |
| Fallback | Source-level default | varies | varies |

**Source-level defaults** (override when no signal is found in text):

| Source | Default WorkMode | Confidence | Reason |
|---|---|---|---|
| `RemoteOK` | `REMOTE` | 0.99 | Only lists remote roles by design |

### Per-source normalization logic

Each source adapter passes specific fields into `infer_work_mode`:

| Source | Signals passed |
|---|---|
| **Greenhouse** | job `location`, job `description` (NLP inference) |
| **Lever** | `categories.workplaceType`, job `location` |
| **Ashby** | `isRemote` boolean (confidence 0.95 if true) |
| **Workable** | `workplace` field: `"remote"→REMOTE`, `"hybrid"→HYBRID`, others→`ONSITE` |
| **RemoteOK** | Source default (always REMOTE, confidence 0.99) |
| **HackerNews** | Comment text, pipe-separated location field |
| **YCombinator** | Company description, `isRemote` hint |
| **WorkAtAStartup** | Job description, location |
| **Wellfound** | Job description, remote tags |
| **GitHubDiscovery** | Repo description (low-confidence; usually UNKNOWN) |
| **AI Discovery** | AI-generated `remote_friendly` / `headquarters` fields |
| **Crunchbase** | HQ location, description |

### Company-level inference

`normalize_company_work_mode()` walks all `open_positions`, runs `infer_work_mode` on each job, then aggregates to a company-level `work_mode`:

- If **all** jobs are remote → company `work_mode = REMOTE`, confidence = min(job confidences)
- If **majority** are remote → company `work_mode = REMOTE`, confidence dampened by hybrid ratio
- If **any** hybrid → `HYBRID`
- If **all** onsite → `ONSITE`
- If **no positions** → infer from company-level fields (description, HQ, culture tags)

`remote_confidence` for non-remote companies is capped at `0.49` to prevent borderline cases from passing the `0.8` threshold.

---

## Discovery Sources — Detailed

### Greenhouse (job board API)

Queries the Greenhouse job board API (`boards.greenhouse.io/v1/boards/{slug}/jobs`) for companies whose tech stacks and role descriptions match the expanded queries. Work mode is inferred from NLP on job `location` and `description` fields — Greenhouse has no explicit remote flag.

### Lever (postings API)

Queries `jobs.lever.co/v0/postings/{company}` for open postings. Uses `categories.workplaceType` when present (values: `"Remote"`, `"Hybrid"`, `"In-person"`). Falls back to location field NLP.

### Ashby (job board API)

Queries `jobs.ashbyhq.com/api/non-user-graphql` for postings. Uses the `isRemote: true/false` boolean field directly with confidence 0.95 (explicit flag from the employer).

### Workable (accounts API)

Queries `apply.workable.com/api/v3/accounts/{slug}/jobs`. Uses the `workplace` field: `"remote"→REMOTE`, `"hybrid"→HYBRID`, everything else→`ONSITE`.

### RemoteOK

`https://remoteok.com/api` — public JSON feed of remote job listings. Every company from this source is treated as `REMOTE` with confidence 0.99. Groups listings by company and matches skill/role tags.

### Hacker News ("Who is Hiring?")

1. Queries Algolia HN API for the latest "Ask HN: Who is hiring?" story (filtered by `created_at_i > 1700000000` to avoid stale threads)
2. Fetches comments for that story ID
3. Parses pipe-delimited comment format: `CompanyName | Role | Location | Remote | ...`
4. Extracts company name via regex: `^([A-Z][A-Za-z0-9 .,&!-]{2,40})\s*\|`
5. Work mode inferred from location field and comment body

### YCombinator Directory

Queries YC's Algolia index (`YCCompany_production`) with `isHiring: true`. Returns company batch, description, funding stage. Falls back to a hardcoded list of well-known YC alumni on API failure.

### Work at a Startup (YC job board)

Scrapes `workatastartup.com/jobs` with BeautifulSoup. Parses job listings for YC-backed companies. Work mode inferred from job description text.

### Wellfound / AngelList

Queries `wellfound.com/jobs` with skill/role filters. Work mode inferred from job metadata and description tags.

### GitHub Discovery

Searches GitHub repos/organizations using the GitHub Search API (`github.com/search/repositories`) to find engineering orgs matching the user's tech stack. Less reliable for work-mode inference (usually returns `UNKNOWN`). Requires `GITHUB_TOKEN`.

### Crunchbase

Queries Crunchbase company search API for companies matching industry/tech keywords. HQ location is the primary work-mode signal.

### AI Discovery (GPT-4o-mini)

Builds a structured prompt from the full user profile and asks the model to generate 10–15 company recommendations as a JSON array. Each entry includes: `name`, `domain`, `description`, `industry`, `size`, `tech_stack`, `funding_stage`, `remote_friendly`, `headquarters`, `culture_tags`. Temperature is set low (0.3) for factual consistency. Falls back to a hardcoded list of 10 tech companies if the API key is not configured.

---

## Hard Constraints Engine

**File:** `backend/services/filters/hard_constraints.py`

### `apply_hard_constraints_with_diagnostics(companies, preferences) → HardConstraintResult`

Central enforcement function. Called in two places:

1. **Discovery pipeline** — in `CompanyDiscoveryService.discover()` and `discover_stream()`, after dedup and industry filter, **before** any company is yielded to `_persist_companies()`. Onsite/hybrid companies that don't match preferences are discarded here and never hit the database.
2. **Workspace reads** — in `GET /company-finder/companies`, the saved workspace rows are re-filtered on every read. This handles companies that were discovered before a preference change (e.g., user later enables strict remote). They become `hidden_by_preferences` without any DB mutation.

### Result shape

```python
@dataclass
class HardConstraintResult:
    visible_companies: list[dict]   # pass all constraints
    hidden_companies:  list[dict]   # blocked, annotated with reasons
    counts_by_source:  dict[str, dict[str, int]]  # telemetry per source
```

### Counts tracked per source

```json
{
  "hard_constraints_filtered": 4,
  "remote_filtered": 0,
  "hybrid_filtered": 2,
  "onsite_filtered": 1,
  "unknown_filtered": 1,
  "blocked_company_filtered": 0,
  "visa_filtered": 0,
  "salary_filtered": 0,
  "location_filtered": 0,
  "visible": 7
}
```

---

## Background Hydration

After minimal records are persisted to Supabase, `_run_background_hydration()` runs as an `asyncio.Task` (fire-and-forget) with four sequential stages:

| Stage | Worker | What it does | SSE event on complete |
|---|---|---|---|
| Enrichment | `run_enrichment_worker()` | Scrapes company website, extracts GitHub org signals, hiring velocity, tech stack depth | `refresh_companies: true` |
| Ranking | `run_ranking_worker()` | Scores each company against profile + preferences using weighted algorithm; persists `ranking_score`, `ranking_explanation`, `ranking_metadata` to `user_companies` | `refresh_companies: true` |
| Contacts | `run_contact_worker()` | Finds hiring managers / founders for top 15 companies; persists to `company_contacts` | `refresh_companies: true` |
| Embeddings | `run_embedding_worker()` | Generates `text-embedding-3-small` vectors; persists to `company_embeddings` for semantic search | — |

Each stage is fault-isolated — failure in enrichment does not block ranking. Stage failures are recorded in `stage_failures` and included in the final SSE event metadata.

### Ranking signals

| Signal | Weight |
|---|---|
| Tech stack overlap | High |
| Role / domain match | High |
| Visa / sponsorship availability | High (when required) |
| Location fit | Medium |
| Remote friendliness (confirmed) | Medium |
| Industry preference | Medium |
| Company size preference | Low–Medium |
| Funding stage / stability | Low |

---

## Workspace Visibility at Read Time

`GET /company-finder/companies` (main.py) applies `partition_workspace_companies()` on every read:

```
DB rows (all saved)
        │
        ├─ archived companies  ──────────────────────────→  archived[]
        │
        └─ active companies
                │
        apply_hard_constraints_with_diagnostics(active, current_prefs)
                │
                ├─ visible_companies  ────────────────────→  companies[]  (returned to UI)
                └─ hidden_companies   ────────────────────→  hidden_by_preferences[]
                                                             (count returned, not full objects)
```

This means toggling strict remote mode immediately hides onsite companies on the next page load without requiring a re-discovery run or DB mutation.

---

## Real-Time Event Streaming

**Endpoint:** `GET /agent-events/stream`

Each browser tab gets its own dedicated event queue. Events are broadcast to all active subscribers.

### Event structure

```json
{
  "id": "uuid",
  "agent_name": "CompanyFinderAgent",
  "task_id": "task-uuid",
  "status": "running",
  "message": "Greenhouse: +12 companies",
  "metadata": {
    "source": "Greenhouse",
    "stage": "company_discovery",
    "refresh_companies": true,
    "source_counts": {
      "raw_discovered": 18,
      "duplicates_removed": 3,
      "hard_constraints_filtered": 3,
      "onsite_filtered": 2,
      "hybrid_filtered": 1,
      "persisted": 12
    },
    "visible_companies": 12
  },
  "created_at": "2026-05-08T10:30:00.000Z"
}
```

### Status values

| Status | Meaning |
|---|---|
| `started` | Pipeline has begun |
| `running` | A step is in progress (message + metadata describe it) |
| `completed` | All background hydration done |
| `error` | A step failed; `metadata.error` contains details |

When `metadata.refresh_companies == true` the frontend re-fetches the workspace endpoint to update the company list incrementally.

---

## Data Persistence

Companies are persisted to Supabase in two tables:

| Table | Content |
|---|---|
| `companies` | Canonical company record (name, domain, description, work_mode, open_positions, …) |
| `user_companies` | User-specific overlay: ranking score, status, contacts found, orchestration stage, work_mode metadata |

`metadata` on both records carries `work_mode`, `remote_confidence`, `work_mode_reasoning`, and `preference_enforcement` so enforcement decisions are auditable.

When Supabase is not configured (`SUPABASE_URL` not set), an in-memory cache (`_user_companies_cache`) is used as a fallback.

---

## Observability

Per-session telemetry is written to `discovery_source_logs.metadata` by `update_discovery_source_log_counts()` after each source batch:

```json
{
  "raw_discovered": 18,
  "duplicates_removed": 3,
  "already_seen_filtered": 1,
  "industry_filtered": 0,
  "hard_constraints_filtered": 3,
  "onsite_filtered": 2,
  "hybrid_filtered": 1,
  "unknown_filtered": 0,
  "ranking_filtered": 0,
  "persistence_failed": 0,
  "persisted": 11
}
```

This lets you audit exactly why companies were dropped at each stage of the pipeline.

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Recommended | AI query expansion + AI Discovery source. Falls back to heuristic queries / hardcoded companies without it. |
| `OPENAI_MODEL` | Optional | Model for AI operations. Defaults to `gpt-4o-mini`. |
| `SUPABASE_URL` | Recommended | Persists companies and workspace state. Falls back to in-memory cache. |
| `SUPABASE_ANON_KEY` | Required with URL | Supabase auth. |
| `GITHUB_TOKEN` | Optional | Enables GitHub Discovery source (org/repo search). |

---

## Architecture Diagram

```
User Browser
    │
    ├── POST /company-finder/run
    │         │
    │         ▼
    │   CompanyFinderAgent.run_full_pipeline()
    │         │
    │   ┌─────┴──────────────────────────────────────────┐
    │   │ Step 1: ResumeParserService (GPT-4o-mini)       │
    │   │ Step 2: normalize_preference_payload()          │
    │   │         + feedback learning merge               │
    │   └─────┬──────────────────────────────────────────┘
    │         │
    │   ┌─────┴──────────────────────────────────────────┐
    │   │ Step 3: CompanyDiscoveryService.discover_stream()│
    │   │                                                 │
    │   │  Phase 1: QueryExpansionService (GPT-4o-mini)   │
    │   │           → N expanded search queries           │
    │   │                                                 │
    │   │  Phase 2: SourceOrchestrator (asyncio, ≤8 conc) │
    │   │  ┌─────────────────────────────────────────┐   │
    │   │  │  Greenhouse   Lever      Ashby           │   │
    │   │  │  Workable     Crunchbase GitHubDiscovery │   │
    │   │  │  RemoteOK     HackerNews YCombinator     │   │
    │   │  │  WorkAtAStartup  Wellfound  AI Discovery  │   │
    │   │  └──────────────────┬──────────────────────┘   │
    │   │                     │ raw company dicts          │
    │   │  Phase 3: Deduplicate by normalized domain       │
    │   │           + RecursiveExpansionService            │
    │   │                                                 │
    │   │  Phase 4: Feedback loop (up to 3 rounds)        │
    │   │           if < 35 companies / < 4 sources        │
    │   │                                                 │
    │   │  Phase 4.5: Industry mismatch filter (soft)     │
    │   │                                                 │
    │   │  Phase 4.6: ◀ HARD CONSTRAINT GATE ▶            │
    │   │  apply_hard_constraints_with_diagnostics()      │
    │   │    • work_mode != remote → BLOCKED              │
    │   │    • remote_confidence < 0.8 → BLOCKED          │
    │   │    • blocked company/domain → BLOCKED           │
    │   │    • sponsorship unavailable → BLOCKED          │
    │   │    • salary below minimum → BLOCKED             │
    │   │    • excluded location → BLOCKED                │
    │   │  visible_companies only pass through ↓          │
    │   │                                                 │
    │   │  Phase 4.7: Remove already-in-workspace domains │
    │   │                                                 │
    │   │  Phase 5: Priority sort (startup score)         │
    │   └─────┬──────────────────────────────────────────┘
    │         │ per-source batches yielded incrementally
    │   ┌─────┴──────────────────────────────────────────┐
    │   │ _persist_companies() per batch                  │
    │   │   upsert companies + user_companies             │
    │   │   store: work_mode, remote_confidence,          │
    │   │          work_mode_reasoning, preference_       │
    │   │          enforcement                            │
    │   └─────┬──────────────────────────────────────────┘
    │         │
    │   ┌─────┴──────────────────────────────────────────┐
    │   │ asyncio.create_task(_run_background_hydration) │
    │   │   run_enrichment_worker()   → website signals  │
    │   │   run_ranking_worker()      → match scores     │
    │   │   run_contact_worker()      → hiring contacts  │
    │   │   run_embedding_worker()    → semantic vectors │
    │   └─────────────────────────────────────────────────┘
    │
    └── GET /agent-events/stream  ←── SSE ←── AgentEventLogger
              (refresh_companies: true on each hydration stage)

    GET /company-finder/companies
              │
        DB rows (all saved companies)
              │
        partition_workspace_companies(rows, current_prefs)
              │
        ┌─────┴────────────────────────────────┐
        │  apply_hard_constraints() on active  │
        │  rows re-enforces preferences on     │
        │  every read (retroactive filtering)  │
        └─────┬────────────────────────────────┘
              │
        visible_companies  →  returned to UI
        hidden_by_preferences  →  count only (no DB mutation)
        archived  →  separate list
```
