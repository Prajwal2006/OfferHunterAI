import { AgentEvent, AgentInfo, Company, Email, PipelineItem } from "./types";

export const MOCK_AGENTS: AgentInfo[] = [
  {
    name: "CompanyFinderAgent",
    displayName: "Company Finder",
    description: "Discovers relevant companies based on your skills",
    status: "completed",
    currentTask: "Found 12 companies matching Python/ML skills",
    icon: "🔍",
  },
  {
    name: "PersonalizationAgent",
    displayName: "Personalization",
    description: "Extracts company insights and personalizes context",
    status: "completed",
    currentTask: "Analyzed Stripe engineering blog",
    icon: "🎯",
  },
  {
    name: "EmailWriterAgent",
    displayName: "Email Writer",
    description: "Generates personalized outreach emails",
    status: "running",
    currentTask: "Drafting email for OpenAI",
    icon: "✍️",
  },
  {
    name: "ResumeTailorAgent",
    displayName: "Resume Tailor",
    description: "Tailors resume bullets for each company",
    status: "idle",
    currentTask: undefined,
    icon: "📄",
  },
  {
    name: "EmailSenderAgent",
    displayName: "Email Sender",
    description: "Sends approved emails via Gmail API",
    status: "idle",
    currentTask: undefined,
    icon: "📧",
  },
  {
    name: "FollowUpAgent",
    displayName: "Follow Up",
    description: "Sends automated follow-ups after no response",
    status: "idle",
    currentTask: undefined,
    icon: "🔄",
  },
  {
    name: "ResponseClassifierAgent",
    displayName: "Response Classifier",
    description: "Classifies and prioritizes email responses",
    status: "idle",
    currentTask: undefined,
    icon: "🧠",
  },
];

export const MOCK_EVENTS: AgentEvent[] = [
  {
    id: "1",
    agent_name: "CompanyFinderAgent",
    task_id: "task-001",
    status: "completed",
    message: "Found 12 companies matching skills: Python, ML, FastAPI",
    metadata: { count: 12, skills: ["Python", "ML", "FastAPI"] },
    created_at: new Date(Date.now() - 300000).toISOString(),
  },
  {
    id: "2",
    agent_name: "PersonalizationAgent",
    task_id: "task-002",
    status: "completed",
    message: "Extracted insights for Stripe — fintech, Series H, 8000 employees",
    metadata: { company: "Stripe", industry: "fintech" },
    created_at: new Date(Date.now() - 240000).toISOString(),
  },
  {
    id: "3",
    agent_name: "PersonalizationAgent",
    task_id: "task-003",
    status: "completed",
    message: "Extracted insights for Vercel — developer tools, unicorn startup",
    metadata: { company: "Vercel", industry: "developer-tools" },
    created_at: new Date(Date.now() - 200000).toISOString(),
  },
  {
    id: "4",
    agent_name: "EmailWriterAgent",
    task_id: "task-004",
    status: "completed",
    message: "Drafted personalized email for Stripe",
    metadata: { company: "Stripe", email_id: "email-001" },
    created_at: new Date(Date.now() - 150000).toISOString(),
  },
  {
    id: "5",
    agent_name: "EmailWriterAgent",
    task_id: "task-005",
    status: "completed",
    message: "Drafted personalized email for Vercel",
    metadata: { company: "Vercel", email_id: "email-002" },
    created_at: new Date(Date.now() - 120000).toISOString(),
  },
  {
    id: "6",
    agent_name: "EmailSenderAgent",
    task_id: "task-006",
    status: "started",
    message: "Waiting for user approval before sending",
    metadata: { pending_count: 3 },
    created_at: new Date(Date.now() - 60000).toISOString(),
  },
  {
    id: "7",
    agent_name: "EmailWriterAgent",
    task_id: "task-007",
    status: "running",
    message: "Drafting email for OpenAI — highlighting ML research background",
    metadata: { company: "OpenAI", step: "writing" },
    created_at: new Date(Date.now() - 10000).toISOString(),
  },
];

export const MOCK_COMPANIES: Company[] = [
  {
    id: "c-001",
    name: "Stripe",
    domain: "stripe.com",
    industry: "Fintech",
    size: "5000-10000",
    relevance_score: 0.95,
    status: "email_drafted",
    created_at: new Date(Date.now() - 300000).toISOString(),
  },
  {
    id: "c-002",
    name: "Vercel",
    domain: "vercel.com",
    industry: "Developer Tools",
    size: "100-500",
    relevance_score: 0.92,
    status: "pending_approval",
    created_at: new Date(Date.now() - 250000).toISOString(),
  },
  {
    id: "c-003",
    name: "OpenAI",
    domain: "openai.com",
    industry: "AI/ML",
    size: "500-1000",
    relevance_score: 0.98,
    status: "personalized",
    created_at: new Date(Date.now() - 200000).toISOString(),
  },
  {
    id: "c-004",
    name: "Anthropic",
    domain: "anthropic.com",
    industry: "AI/ML",
    size: "100-500",
    relevance_score: 0.97,
    status: "discovered",
    created_at: new Date(Date.now() - 150000).toISOString(),
  },
  {
    id: "c-005",
    name: "Supabase",
    domain: "supabase.com",
    industry: "Developer Tools",
    size: "50-100",
    relevance_score: 0.89,
    status: "sent",
    created_at: new Date(Date.now() - 600000).toISOString(),
  },
];

export const MOCK_EMAILS: Email[] = [
  {
    id: "email-001",
    company_id: "c-001",
    company_name: "Stripe",
    subject: "Experienced ML Engineer — Excited About Stripe's Infrastructure Challenges",
    body: `Hi [Hiring Manager],

I came across Stripe's engineering blog post about your real-time fraud detection system, and I was genuinely impressed by the scale of the problem you're solving — processing millions of transactions per second while maintaining sub-50ms latency.

I'm a full-stack engineer with 4 years of experience in Python, FastAPI, and machine learning systems. At my previous role at a Series B fintech startup, I built a real-time anomaly detection pipeline that reduced false positives by 40% using gradient boosting models served via a custom inference engine.

I'd love to explore how my experience could contribute to Stripe's ML infrastructure team. Would you be open to a 20-minute call this week?

Best,
[Your Name]`,
    status: "pending_approval",
    created_at: new Date(Date.now() - 150000).toISOString(),
    recipient_email: "eng-recruiting@stripe.com",
  },
  {
    id: "email-002",
    company_id: "c-002",
    company_name: "Vercel",
    subject: "Next.js Developer Passionate About Edge Computing & DX",
    body: `Hi [Hiring Manager],

As someone who's been building with Next.js since v9, Vercel's work on Edge Runtime and the App Router has been transformative for how I think about web architecture.

I'm a full-stack engineer with deep expertise in Next.js, TypeScript, and distributed systems. I recently built a multi-tenant SaaS platform on Vercel that serves 50k monthly active users with zero cold-starts using Edge Functions.

The work your team is doing on the v0 AI and the new rendering primitives is exactly the kind of developer-first innovation I want to be part of. I'd love to chat about how I could contribute to the DX engineering team.

Best,
[Your Name]`,
    status: "pending_approval",
    created_at: new Date(Date.now() - 120000).toISOString(),
    recipient_email: "careers@vercel.com",
  },
  {
    id: "email-003",
    company_id: "c-005",
    company_name: "Supabase",
    subject: "Open Source Enthusiast — Contributing to the Postgres Ecosystem",
    body: `Hi [Hiring Manager],

I've been a huge fan of Supabase since the early days — I've deployed it for 3 production applications and even contributed a minor fix to supabase-js last year.

I specialize in PostgreSQL, real-time systems, and developer tooling. I built a CDC (Change Data Capture) pipeline using Supabase Realtime that now powers a live collaboration feature for 10k+ users.

The mission of making Postgres accessible to every developer resonates deeply with me. I'd be honored to contribute to the platform itself.

Best,
[Your Name]`,
    status: "sent",
    created_at: new Date(Date.now() - 600000).toISOString(),
    sent_at: new Date(Date.now() - 500000).toISOString(),
    recipient_email: "jobs@supabase.com",
  },
];

export const MOCK_PIPELINE: PipelineItem[] = MOCK_COMPANIES.map((company) => ({
  id: `pipeline-${company.id}`,
  company,
  email: MOCK_EMAILS.find((e) => e.company_id === company.id),
  created_at: company.created_at,
  steps: [
    {
      agent: "CompanyFinder",
      status: "completed",
      timestamp: company.created_at,
      message: `Discovered ${company.name}`,
    },
    {
      agent: "Personalization",
      status:
        company.status === "discovered"
          ? "pending"
          : "completed",
      timestamp:
        company.status !== "discovered"
          ? new Date(
              new Date(company.created_at).getTime() + 30000
            ).toISOString()
          : undefined,
      message:
        company.status !== "discovered"
          ? `Analyzed ${company.name} culture & tech stack`
          : undefined,
    },
    {
      agent: "EmailWriter",
      status:
        company.status === "discovered" || company.status === "personalized"
          ? "pending"
          : "completed",
      timestamp:
        company.status !== "discovered" && company.status !== "personalized"
          ? new Date(
              new Date(company.created_at).getTime() + 60000
            ).toISOString()
          : undefined,
      message:
        company.status !== "discovered" && company.status !== "personalized"
          ? `Drafted email for ${company.name}`
          : undefined,
    },
    {
      agent: "Review",
      status:
        company.status === "pending_approval"
          ? "running"
          : company.status === "sent" || company.status === "replied"
          ? "completed"
          : "pending",
      timestamp:
        company.status === "sent"
          ? new Date(
              new Date(company.created_at).getTime() + 90000
            ).toISOString()
          : undefined,
      message:
        company.status === "sent"
          ? "Approved by user"
          : company.status === "pending_approval"
          ? "Awaiting approval"
          : undefined,
    },
    {
      agent: "Sender",
      status:
        company.status === "sent" || company.status === "replied"
          ? "completed"
          : "pending",
      timestamp:
        company.status === "sent"
          ? new Date(
              new Date(company.created_at).getTime() + 120000
            ).toISOString()
          : undefined,
      message:
        company.status === "sent"
          ? `Email sent to ${company.domain}`
          : undefined,
    },
  ],
}));
