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
