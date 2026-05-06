# Company Finder Agent

The Company Finder Agent is OfferHunterAI's core intelligence layer for proactively discovering and ranking companies that match a user's resume, skills, and job preferences — without the user having to search manually.

---

## How It Works: The 5-Step Pipeline

Every time the Company Finder runs, it executes a sequential pipeline, emitting real-time progress events via Server-Sent Events (SSE) at each step.

```
Resume Parse  →  Preference Collection  →  Multi-Source Discovery  →  Ranking & Scoring  →  Contact Discovery
```

### Step 1 — Resume Parsing

The `ResumeParserService` extracts structured data from the user's uploaded resume:

- **Skills & tech stack** — extracted via regex heuristics and an AI pass (GPT-4o-mini)
- **Work experience** — titles, companies, dates, descriptions
- **Education** — degrees, institutions
- **Inferred profile** — seniority level, preferred domains, years of experience

If a resume has already been parsed (stored in Supabase), this step is skipped.

### Step 2 — Preference Collection

The user completes the structured 14-step Preference Wizard in the frontend. Preferences include:

| Preference | Examples |
|---|---|
| Target roles | Software Engineer, ML Engineer, DevOps |
| Work mode | Remote / Hybrid / Onsite |
| Locations | US, UK, Canada, EU |
| Employment type | Full-time, Contract |
| Salary range | $120k–$180k |
| Company size | Startup (1–50), Scale-up (51–500), Large (500+) |
| Industries | AI/ML, Fintech, Healthcare, SaaS |
| Sponsorship needed | Yes / No |
| Career priorities | Compensation, Growth, Mission, Work-life balance, etc. |

Preferences are saved to Supabase and passed directly into the discovery pipeline.

### Step 3 — Multi-Source Discovery

The `CompanyDiscoveryService` runs **four sources in parallel** using `asyncio.gather()`, then deduplicates and merges the results.

See the [Internet Scraping Sources](#internet-scraping-sources) section below for full details on each source.

### Step 4 — Weighted Ranking & Scoring

The `CompanyRankerService` scores every discovered company against the user's profile and preferences using a weighted algorithm:

| Signal | Weight |
|---|---|
| Tech stack overlap | High |
| Role/domain match | High |
| Location fit | Medium |
| Remote friendliness | Medium |
| Company size preference | Low–Medium |
| Visa/sponsorship availability | High (when required) |
| Industry preference | Medium |
| Funding stage / stability | Low |

Companies are sorted by composite score and the top N are returned (default: 25–50).

### Step 5 — Contact Discovery

The `ContactFinderService` attempts to find a relevant hiring contact or engineering leader at each ranked company. Results are attached to the company object for use by the Email Writer Agent.

---

## Internet Scraping Sources

### 1. Hacker News — "Who is Hiring?" Threads

**URL:** `https://hn.algolia.com/api/v1/search`  
**Cost:** Free, no API key required  
**Update frequency:** Monthly (HN posts a new hiring thread each month)

**How it works:**
1. Queries the Algolia HN API for the latest "Ask HN: Who is hiring?" story post
2. Searches comments on that specific story thread that match the user's skills and target roles
3. Parses hiring post comments using the standard HN format:
   ```
   CompanyName | Role | Location | Remote | Description...
   ```
4. Extracts company names via pipe-pattern regex: `^([A-Z][A-Za-z0-9 .,&!-]{2,40})\s*\|`

**Strengths:** Real, actively-hiring companies posting directly on HN. Strong signal for tech startups, YC-backed companies, and engineering-led orgs.

**Limitations:** Only captures companies that manually post on HN; skews toward engineering roles and startup culture.

---

### 2. RemoteOK

**URL:** `https://remoteok.com/api`  
**Cost:** Free public API, no authentication  
**Update frequency:** Near real-time job postings

**How it works:**
1. Fetches the public JSON feed of remote job listings
2. Groups listings by company name
3. Filters companies whose listed roles and tags overlap with the user's skills and target roles
4. Extracts company metadata: name, website URL, open positions, remote status

**Strengths:** Exclusively remote-friendly companies. Strong signal that the company actively hires remotely. Rich job tag data (React, Python, Go, etc.) enables precise skill matching.

**Limitations:** Only covers companies advertising remote roles at the time of the request. Smaller and mid-size companies are over-represented.

---

### 3. Y Combinator Companies Directory

**URL:** `https://45bwzj1sgc-dsn.algolia.net` (Algolia index: `YCCompany_production`)  
**Cost:** Free public API (no key required for basic search)  
**Update frequency:** Maintained by YC, updated as companies apply/graduate

**How it works:**
1. Queries YC's Algolia-backed company search API
2. Filters for `isHiring: true` to return only actively hiring companies
3. Searches across company name, description, tags, and batch (e.g., W24, S23)
4. Maps results to the standard company schema

**Fallback:** If the YC API is unreachable, a hardcoded list of 12 well-known YC alumni companies is used (Airbnb, Stripe, Dropbox, etc.).

**Strengths:** High-quality companies with known funding, mission, and growth trajectory. YC brand is a strong signal for engineering culture and growth opportunities.

**Limitations:** Only covers YC-funded companies (~4,000 total). Not representative of the broader job market.

---

### 4. AI-Powered Discovery (OpenAI GPT-4o-mini)

**Model:** `gpt-4o-mini` (configurable via `OPENAI_MODEL` env var)  
**Cost:** OpenAI API usage (paid)  
**Update frequency:** Per-request, based on model's training data

**How it works:**
1. Builds a structured prompt from the user's full profile: skills, experience, preferences, salary range, location, target roles
2. Asks GPT-4o-mini to generate a JSON array of 10–15 companies that would be a strong match
3. Each company in the response includes: name, domain, description, industry, size, tech stack, funding stage, remote status, headquarters, culture tags
4. Parses the structured JSON response and normalizes to the standard company schema

**Prompt strategy:** The prompt explicitly instructs the model to output valid JSON only, specifying the exact schema fields. Temperature is kept low (0.3) to produce consistent, factual results rather than creative hallucinations.

**Fallback:** If `OPENAI_API_KEY` is not configured or the API call fails, a hardcoded list of 10 well-known tech companies is used:

> OpenAI, Anthropic, DeepMind, Cohere, Mistral AI, Databricks, Hugging Face, Figma, Notion, Cloudflare

**Strengths:** Most personalized source. Can reason across all user signals simultaneously. Surfaces niche companies that don't post on job boards. Especially effective for specialized roles (AI/ML, research, DevRel, etc.).

**Limitations:** Dependent on model training data cutoff — may not know about companies founded after the cutoff. Requires a paid OpenAI API key for production use.

---

## Real-Time Event Streaming

The agent communicates its progress to the frontend via **Server-Sent Events (SSE)**.

**Endpoint:** `GET /agent-events/stream`

Each connected client (browser tab) gets its own dedicated event queue. Events are **broadcast** to all active subscribers simultaneously — opening the Agents page and the Company Finder page at the same time will not cause either to miss events.

### Event structure

```json
{
  "id": "uuid",
  "agent_name": "CompanyFinderAgent",
  "task_id": "task-uuid",
  "status": "in_progress",
  "message": "Searching HackerNews Who's Hiring...",
  "metadata": {},
  "created_at": "2024-01-15T10:30:00.000Z"
}
```

### Status values

| Status | Meaning |
|---|---|
| `started` | Pipeline has begun |
| `in_progress` | A step is running (message describes the step) |
| `completed` | All steps finished; `metadata.companies` contains the full ranked list |
| `error` | A step failed; `metadata.error` contains details |

### Completed event payload

When the pipeline finishes, the `completed` event's `metadata` includes the full company objects so the frontend can render results immediately without a separate API round-trip:

```json
{
  "status": "completed",
  "metadata": {
    "companies": [ ...full company objects... ],
    "company_names": ["Anthropic", "Figma", "Notion", ...],
    "total": 25
  }
}
```

---

## Data Persistence

Discovered and ranked companies are persisted to **Supabase** for retrieval across sessions. When Supabase is not configured (no `SUPABASE_URL` env var), the backend maintains an **in-memory cache** (`_user_companies_cache`) keyed by `user_id`. The frontend always prefers companies delivered directly in the SSE `completed` event, avoiding any dependency on the database for the initial render.

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Optional | Enables AI-powered discovery (Step 4). Without it, 10 fallback companies are used. |
| `OPENAI_MODEL` | Optional | Model for AI discovery. Defaults to `gpt-4o-mini`. |
| `SUPABASE_URL` | Optional | Persists company rankings across sessions. Without it, in-memory cache is used. |
| `SUPABASE_ANON_KEY` | Optional | Required alongside `SUPABASE_URL`. |
| `GITHUB_TOKEN` | Optional | Reserved for future GitHub org search source. |

---

## Architecture Diagram

```
User Browser
    │
    ├── POST /company-finder/run  ──────────────────────────────────────────┐
    │                                                                        │
    └── GET /agent-events/stream  ←── SSE broadcast ←── AgentEventLogger ←─┤
                                                                            │
                                                               CompanyFinderAgent
                                                                    │
                                          ┌─────────────────────────┤
                                          │                         │
                                    asyncio.gather()          AgentEventLogger
                                          │                   (emits SSE events)
                          ┌───────────────┼───────────────────────┐
                          │               │               │       │
                   HN Algolia      RemoteOK API     YC Algolia   OpenAI
                   (comments       (job feed)      (companies)  (gpt-4o-mini)
                   on hiring
                   threads)
                          │               │               │       │
                          └───────────────┴───────────────┴───────┘
                                          │
                                  Deduplicate & Merge
                                          │
                                  CompanyRankerService
                                  (weighted scoring)
                                          │
                                  ContactFinderService
                                          │
                               ┌──────────┴──────────┐
                               │                     │
                          Supabase             In-memory cache
                          (persist)           (fallback when
                                              DB not configured)
```
