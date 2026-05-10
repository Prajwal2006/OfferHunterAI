export type AgentStatus = "idle" | "running" | "completed" | "error";

export interface AgentEvent {
  id: string;
  agent_name: string;
  task_id: string;
  status: "started" | "running" | "completed" | "failed";
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AgentInfo {
  name: string;
  displayName: string;
  description: string;
  status: AgentStatus;
  currentTask?: string;
  lastEvent?: AgentEvent;
  icon: string;
}

export interface Company {
  id: string;
  name: string;
  domain: string;
  industry: string;
  size: string;
  relevance_score: number;
  status: "discovered" | "personalized" | "email_drafted" | "pending_approval" | "sent" | "replied" | "followed_up";
  created_at: string;
  // Extended fields
  logo_url?: string;
  description?: string;
  mission?: string;
  tech_stack?: string[];
  funding_stage?: string;
  founded_year?: number;
  headquarters?: string;
  website_url?: string;
  linkedin_url?: string;
  hiring_status?: "actively_hiring" | "hiring" | "unknown" | "not_hiring";
  remote_friendly?: boolean;
  work_mode?: "remote" | "hybrid" | "onsite" | "unknown";
  remote_confidence?: number;
  work_mode_reasoning?: string[];
  sponsorship_available?: boolean;
  open_positions?: JobPosition[];
  recent_news?: NewsItem[];
  culture_tags?: string[];
  source?: string;
  application_strategy?: string;
  // Joined data
  ranking?: CompanyRanking;
  match_score?: number;
  company_contacts?: CompanyContact[];
  contacts?: CompanyContact[];
  workspace?: WorkspaceCompanyState;
  preference_enforcement?: PreferenceEnforcement;
}

export interface PreferenceEnforcement {
  hidden_by_preferences?: boolean;
  reasons?: string[];
  filtered_job_count?: number;
  filtered_jobs?: Array<{
    title: string;
    work_mode: string;
    reasons: string[];
  }>;
}

export interface CompanyRanking {
  match_score: number;
  resume_match: number;
  skills_match: number;
  interests_match: number;
  location_match: number;
  compensation_match: number;
  tech_stack_match: number;
  visa_compatibility: number;
  hiring_likelihood: number;
  company_size_match?: number;
  semantic_similarity?: number;
  semantic_relevance?: number;
  novelty_score?: number;
  diversity_score?: number;
  exploration_score?: number;
  hiring_signal_score?: number;
  feedback_alignment?: number;
  exploration_reason?: string;
  match_explanation: string;
  strengths: string[];
  gaps: string[];
  suggestions: string[];
}

export interface WorkspaceCompanyState {
  id?: string;
  source?: string;
  discovered_at?: string;
  status?: string;
  orchestration_stage?: string;
  liked?: boolean | null;
  disliked?: boolean | null;
  archived?: boolean;
  removed?: boolean;
  manually_added?: boolean;
  personalization_completed?: boolean;
  outreach_started?: boolean;
  outreach_sent?: boolean;
  notes?: string;
  application_strategy?: string;
  ranking_score?: number;
  ranking_explanation?: string;
  hidden_by_preferences?: boolean;
}

export interface DiscoverySession {
  id: string;
  user_id: string;
  status: "running" | "completed" | "failed" | "paused";
  queries_used?: string[];
  sources_used?: string[];
  companies_found?: number;
  total_companies_found?: number;
  embedding_version?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface DiscoverySourceLog {
  id: string;
  user_id: string;
  discovery_session_id?: string;
  source: string;
  query_used?: string[];
  status: "running" | "success" | "failed" | "timeout";
  result_count: number;
  duplicate_count?: number;
  filtered_count?: number;
  error?: string;
  duration_ms?: number;
  metadata?: {
    raw_discovered?: number;
    duplicates_removed?: number;
    already_seen_filtered?: number;
    ranking_filtered?: number;
    persistence_failed?: number;
    persisted?: number;
    [key: string]: unknown;
  };
  started_at?: string;
  completed_at?: string;
}

export interface OrchestrationState {
  user_id: string;
  current_stage: OrchestrationStepId | string;
  progress: Record<string, unknown>;
  active_agents: string[];
  paused_state: boolean;
  last_task_id?: string;
  updated_at?: string;
  created_at?: string;
}

export interface CompanyContact {
  id?: string;
  company_id?: string;
  name: string;
  title: string;
  email: string;
  linkedin_url?: string;
  contact_type: "recruiter" | "founder" | "hiring_manager" | "engineer" | "hr" | "other";
  confidence: number;
  verified: boolean;
  source?: string;
}

export interface JobPosition {
  title: string;
  url?: string;
  location?: string;
  work_mode?: string;
  remote_confidence?: number;
  work_mode_reasoning?: string[];
  employment_type?: string;
  salary_range?: string;
  posted_at?: string;
}

export interface NewsItem {
  title: string;
  url?: string;
  date?: string;
  summary?: string;
}

export interface ParsedProfile {
  id?: string;
  user_id: string;
  full_name: string;
  email: string;
  phone: string;
  location: string;
  citizenship: string;
  education: EducationEntry[];
  gpa: string;
  skills: string[];
  tech_stack: string[];
  certifications: string[];
  work_experience: WorkExperience[];
  projects: Project[];
  leadership: string[];
  research: string[];
  awards: string[];
  preferred_domains: string[];
  keywords: string[];
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  other_links: string[];
  created_at?: string;
}

export interface EducationEntry {
  institution: string;
  degree: string;
  field: string;
  graduation_date: string;
  gpa: string;
}

export interface WorkExperience {
  company: string;
  title: string;
  location: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  bullets: string[];
}

export interface Project {
  name: string;
  description: string;
  tech_used: string[];
  url: string;
}

export interface UserPreferences {
  id?: string;
  user_id: string;
  preferred_roles: string[];
  preferred_locations: string[];
  open_to_relocation?: boolean;
  work_mode?: "remote" | "hybrid" | "onsite" | "flexible";
  employment_type: string[];
  salary_min?: number;
  salary_max?: number;
  open_to_startups?: boolean;
  company_size_pref: string[];
  industries_of_interest: string[];
  sponsorship_required?: boolean;
  work_authorization?: string;
  graduation_date?: string;
  earliest_start?: string;
  preferred_tech_stack: string[];
  career_priorities: Record<string, number>;
  avoided_companies: string[];
  avoided_industries: string[];
  open_to_cold_outreach: boolean;
  profile_links: Record<string, string>;
  conversation_complete: boolean;
}

export interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
}

export interface Email {
  id: string;
  company_id: string;
  company_name: string;
  subject: string;
  body: string;
  status: "pending_approval" | "approved" | "sent" | "rejected";
  created_at: string;
  sent_at?: string;
  recipient_email?: string;
  resume_version_id?: string | null;
  resume_skills?: string[];
}

export interface PersonalizationProfile {
  id: string;
  user_id: string;
  company_id: string;
  fit_score: number;
  outreach_type: string;
  tone: string;
  company_alignment: string[];
  relevant_projects: Array<Record<string, unknown>>;
  relevant_skills: string[];
  suggested_links: Array<{ type?: string; url?: string; reason?: string }>;
  recommended_hooks: string[];
  email_strategy: Record<string, unknown>;
  key_points_to_mention: string[];
  personalization_summary: string;
  evidence?: Record<string, unknown>;
}

export interface OutreachContact {
  id?: string;
  user_id?: string;
  company_id?: string;
  name: string;
  role: string;
  title?: string;
  email: string;
  confidence: number;
  source: string;
  priority_score: number;
  verified: boolean;
  contact_type: "recruiter" | "founder" | "hiring_manager" | "engineer" | "hr" | "other";
}

export interface EmailDraft {
  id: string;
  user_id: string;
  company_id: string;
  company_name: string;
  outreach_type: string;
  tone: string;
  selected_variant: string;
  subject: string;
  body: string;
  variants: Record<string, string>;
  subjects: Array<{ label: string; subject: string; selected?: boolean }>;
  recipient_email?: string;
  status: "draft" | "pending_approval" | "approved" | "rejected" | "scheduled" | "sent" | "failed";
  version_number: number;
  resume_version_id?: string | null;
  resume_skills?: string[];
  generation_metadata?: Record<string, unknown>;
  companies?: Partial<Company>;
  created_at?: string;
  updated_at?: string;
  last_edited_at?: string;
}

export interface EmailVersion {
  id: string;
  draft_id: string;
  version_number: number;
  subject: string;
  body: string;
  selected_variant: string;
  recipient_email?: string;
  event_type: string;
  editor: "user" | "ai" | "system";
  changes?: Record<string, unknown>;
  created_at: string;
}

export interface ResumeVersion {
  id: string;
  user_id: string;
  file_name: string;
  version_label: string;
  extracted_text: string;
  extracted_skills: string[];
  is_active: boolean;
  created_at: string;
}

export interface PipelineItem {
  id: string;
  company: Company;
  email?: Email;
  steps: PipelineStep[];
  created_at: string;
}

export interface PipelineStep {
  agent: string;
  status: "pending" | "running" | "completed" | "failed";
  timestamp?: string;
  message?: string;
}

export type OrchestrationStepId =
  | "CompanyFinder"
  | "Personalization"
  | "EmailWriter"
  | "Review"
  | "Sender";

export interface OrchestrationStep {
  id: OrchestrationStepId;
  label: string;
  description: string;
  status: "pending" | "active" | "completed";
}

export interface AgentRunStatus {
  task_id: string;
  status: "started" | "running" | "completed" | "failed";
}

