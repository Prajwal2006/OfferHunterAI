# ⚡ OfferHunter AI

**A production-grade multi-agent GenAI system** for automated job discovery, personalized outreach, and pipeline tracking — with a strict human-in-the-loop approval step before any email is sent.

---

## 🎯 What It Does

| Feature | Description |
|---|---|
| 🔍 **Company Discovery** | AI finds companies relevant to your skills & job title |
| 🎯 **Personalization** | Extracts company insights, tech stack, culture signals |
| ✍️ **Email Writing** | GPT-4 generates personalized cold outreach emails |
| 🔒 **Human Review** | YOU approve every email before it's sent — non-negotiable |
| 📧 **Gmail Sending** | Sends via Gmail API (OAuth2) only after approval |
| 🔄 **Follow-Ups** | Auto follow-ups if no reply (with your approval) |
| 🧠 **Response Classification** | Classifies replies as positive/neutral/negative |
| 📡 **Real-time Dashboard** | Live agent activity monitoring with SSE streaming |

---

## 🖥️ Screenshots

### Dashboard
The main dashboard showing agent status, live events, and pipeline stats.

### Agent Activity Dashboard
Real-time orchestration flow, live agent status panel, event stream with filtering, and per-company task timeline.

### Email Review (Human-in-the-Loop)
Review, edit, approve, or reject AI-drafted emails. Zero emails sent without explicit approval.

### Pipeline (CRM Board)
Kanban-style board and list view showing every company's outreach stage.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js)                │
│  Dashboard │ Agent Activity │ Review │ Pipeline     │
└─────────────────────┬───────────────────────────────┘
                      │ REST + SSE
┌─────────────────────▼───────────────────────────────┐
│                  BACKEND (FastAPI)                  │
│  /agents/run │ /agent-events │ /emails │ /pipeline  │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│                  AGENT LAYER (CrewAI)               │
│  CompanyFinder → Personalization → EmailWriter      │
│  ResumeTailor │ EmailSender │ FollowUp │ Classifier │
└──────┬──────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│              DATABASE (Supabase/PostgreSQL)         │
│  agent_events │ companies │ emails │ follow_ups     │
└─────────────────────────────────────────────────────┘
```

---

## 🤖 Agent System

| Agent | Role | Status Emitted |
|---|---|---|
| `CompanyFinderAgent` | Discovers relevant companies via LinkedIn, HN, Crunchbase | started → running → completed |
| `PersonalizationAgent` | Scrapes company sites for insights & culture signals | started → running → completed |
| `EmailWriterAgent` | Generates personalized outreach via GPT-4 | started → running → completed |
| `ResumeTailorAgent` | Tailors resume bullets per company | started → running → completed |
| `EmailSenderAgent` | Sends ONLY approved emails via Gmail API | started → running → completed |
| `FollowUpAgent` | Drafts follow-ups after no response (needs approval) | started → running → completed |
| `ResponseClassifierAgent` | Classifies replies as positive/neutral/negative | started → running → completed |

Every agent emits structured events to:
1. **SSE stream** → Real-time frontend updates
2. **Supabase `agent_events` table** → Persistent audit trail

---

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- Python 3.12+
- Supabase account
- OpenAI API key
- Google Cloud project (Gmail API)

### 1. Clone and Install

```bash
git clone https://github.com/Prajwal2006/OfferHunterAI.git
cd OfferHunterAI

# Frontend
cd frontend
npm install

# Backend
cd ../backend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Root .env
# Windows:
copy .env.example .env
# macOS/Linux:
# cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, GMAIL_*

# Frontend .env.local
# Windows:
copy frontend\.env.example frontend\.env.local
# macOS/Linux:
# cp frontend/.env.example frontend/.env.local
# Fill in: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### 3. Set Up Database

Run the migration in your Supabase SQL editor:
```bash
supabase/migrations/001_initial_schema.sql
```

### 4. Run

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 5. Docker Compose (alternative)

```bash
# Windows:
copy .env.example .env  # fill in values
# macOS/Linux:
# cp .env.example .env  # fill in values
docker compose up
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/agents/run` | Trigger full agent pipeline |
| `POST` | `/agents/{name}/execute` | Execute specific agent |
| `GET` | `/agent-events` | Poll recent agent events |
| `GET` | `/agent-events/stream` | SSE stream of live events |
| `GET` | `/emails` | List emails (with optional `?status=` filter) |
| `PATCH` | `/emails/{id}` | Edit email draft |
| `POST` | `/emails/{id}/approve` | ✅ Approve email (human-in-the-loop) |
| `POST` | `/emails/{id}/reject` | ❌ Reject email |
| `POST` | `/emails/{id}/send` | Send approved email via Gmail |
| `GET` | `/pipeline` | Full outreach pipeline |
| `GET` | `/health` | Health check |

---

## 🗄️ Database Schema

```sql
-- Real-time agent observability
agent_events (id, agent_name, task_id, status, message, metadata, created_at)

-- Company discovery
companies (id, name, domain, industry, size, relevance_score, status, metadata)

-- Outreach emails (human-in-the-loop required)
emails (id, company_id, subject, body, status, sent_at, gmail_message_id)

-- Follow-up tracking
follow_ups (id, email_id, follow_up_number, body, status, scheduled_at)
```

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router), TypeScript, Tailwind CSS, Framer Motion |
| **Backend** | Python 3.12, FastAPI, uvicorn |
| **Agents** | CrewAI, LangChain, OpenAI GPT-4 |
| **Database** | Supabase (PostgreSQL + Realtime) |
| **Realtime** | Server-Sent Events (SSE) |
| **Email** | Gmail API (OAuth2) |
| **Icons** | Lucide React |

---

## 🔒 Human-in-the-Loop (Critical)

**Emails are NEVER sent automatically.** The flow is:

```
AI generates email
       ↓
Stored with status = pending_approval
       ↓
Shown in Review Page
       ↓
User reads, edits if needed, then clicks Approve
       ↓
EmailSenderAgent sends via Gmail API
```

The `EmailSenderAgent` checks the email's `status` field before sending.
If it's not `approved`, the send is **blocked**.

---

## 📜 License

MIT
