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
  sponsorship_available?: boolean;
  open_positions?: JobPosition[];
  recent_news?: NewsItem[];
  culture_tags?: string[];
  source?: string;
  // Joined data
  ranking?: CompanyRanking;
  match_score?: number;
  company_contacts?: CompanyContact[];
  contacts?: CompanyContact[];
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
  match_explanation: string;
  strengths: string[];
  gaps: string[];
  suggestions: string[];
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

