const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export function buildApiUrl(path: string): string {
  return `${API_URL}/${path.replace(/^\/+/, "")}`;
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init?: RequestInit,
  timeoutMs = 10_000
) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

export interface CompanyWorkspaceResponse {
  companies: import("./types").Company[];
  visible_companies?: import("./types").Company[];
  hidden_by_preferences?: import("./types").Company[];
  archived_companies?: import("./types").Company[];
  total: number;
}

export async function fetchAgentEvents(limit = 50) {
  const res = await fetch(buildApiUrl(`/agent-events?limit=${limit}`));
  if (!res.ok) throw new Error("Failed to fetch agent events");
  return res.json();
}

export async function runAgents(payload: {
  skills: string[];
  job_title: string;
  company_count?: number;
  resume_text?: string;
  resume_version_id?: string;
}) {
  const res = await fetch(`${API_URL}/agents/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to run agents");
  return res.json();
}

export async function executeAgent(
  agentName: string,
  payload: Record<string, unknown>
) {
  const res = await fetch(`${API_URL}/agents/${agentName}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to execute agent ${agentName}`);
  return res.json();
}

export async function fetchEmails(status?: string) {
  const url = status
    ? `${API_URL}/emails?status=${status}`
    : `${API_URL}/emails`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch emails");
  return res.json();
}

export async function generatePersonalization(payload: {
  user_id: string;
  company_id: string;
  job?: Record<string, unknown>;
}) {
  const res = await fetch(`${API_URL}/outreach/personalization`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to generate personalization");
  return res.json() as Promise<{ profile: import("./types").PersonalizationProfile }>;
}

export async function fetchPersonalization(companyId: string, userId: string) {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetchWithTimeout(`${API_URL}/outreach/personalization/${companyId}?${params}`, undefined, 6_000);
  if (!res.ok) throw new Error("Failed to fetch personalization");
  return res.json() as Promise<{ profile: import("./types").PersonalizationProfile | null }>;
}

export async function discoverOutreachContacts(payload: {
  user_id: string;
  company_id: string;
  job?: Record<string, unknown>;
}) {
  const res = await fetch(`${API_URL}/outreach/contacts/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to discover contacts");
  return res.json() as Promise<{ contacts: import("./types").OutreachContact[] }>;
}

export async function fetchOutreachContacts(companyId: string, userId: string) {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetchWithTimeout(`${API_URL}/outreach/contacts/${companyId}?${params}`, undefined, 6_000);
  if (!res.ok) throw new Error("Failed to fetch contacts");
  return res.json() as Promise<{ contacts: import("./types").OutreachContact[] }>;
}

export async function generateEmailDraft(payload: {
  user_id: string;
  company_id: string;
  job?: Record<string, unknown>;
  recipient?: Record<string, unknown>;
  outreach_type?: string;
}) {
  let res: Response;
  try {
    res = await fetchWithTimeout(`${API_URL}/outreach/drafts/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, 90_000);
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Draft generation timed out. Please try again.");
    }
    throw err;
  }
  if (!res.ok) {
    let detail = "Failed to generate draft";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // keep fallback
    }
    throw new Error(detail);
  }
  return res.json() as Promise<{
    draft: import("./types").EmailDraft;
    personalization: import("./types").PersonalizationProfile;
  }>;
}

export async function fetchEmailDrafts(userId: string, status?: string) {
  const params = new URLSearchParams({ user_id: userId });
  if (status) params.set("status", status);
  const res = await fetchWithTimeout(`${API_URL}/outreach/drafts?${params}`, undefined, 8_000);
  if (!res.ok) throw new Error("Failed to fetch drafts");
  return res.json() as Promise<{ drafts: import("./types").EmailDraft[] }>;
}

export async function fetchEmailDraft(draftId: string) {
  const res = await fetchWithTimeout(`${API_URL}/outreach/drafts/${draftId}`, undefined, 8_000);
  if (!res.ok) throw new Error("Failed to fetch draft");
  return res.json() as Promise<{
    draft: import("./types").EmailDraft;
    versions: import("./types").EmailVersion[];
    subjects: Array<{ label: string; subject: string }>;
  }>;
}

export async function updateEmailDraft(
  draftId: string,
  updates: {
    user_id?: string;
    subject?: string;
    body?: string;
    selected_variant?: string;
    recipient_email?: string;
    status?: string;
  }
) {
  const res = await fetchWithTimeout(`${API_URL}/outreach/drafts/${draftId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  }, 8_000);
  if (!res.ok) throw new Error("Failed to update draft");
  return res.json() as Promise<{ draft: import("./types").EmailDraft; version?: import("./types").EmailVersion }>;
}

export async function requestInlineAIEdit(
  draftId: string,
  payload: {
    user_id: string;
    instruction: string;
    selected_text: string;
    full_body: string;
    subject?: string;
    auto_apply?: boolean;
  }
) {
  const res = await fetchWithTimeout(`${API_URL}/outreach/drafts/${draftId}/ai-edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, 20_000);
  if (!res.ok) throw new Error("Failed to create AI edit");
  return res.json() as Promise<{
    ai_edit_request_id: string;
    original_text: string;
    replacement_text: string;
    updated_body: string;
    diff: string;
    rationale: string;
    applied: boolean;
  }>;
}

export async function restoreEmailVersion(draftId: string, versionId: string, userId: string) {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetch(`${API_URL}/outreach/drafts/${draftId}/versions/${versionId}/restore?${params}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to restore version");
  return res.json() as Promise<{ draft: import("./types").EmailDraft }>;
}

export async function compareEmailVersions(
  draftId: string,
  leftVersionId: string,
  rightVersionId: string
) {
  const params = new URLSearchParams({
    left_version_id: leftVersionId,
    right_version_id: rightVersionId,
  });
  const res = await fetch(`${API_URL}/outreach/drafts/${draftId}/versions/compare?${params}`);
  if (!res.ok) throw new Error("Failed to compare versions");
  return res.json() as Promise<{
    subject_changed: boolean;
    body_diff: string;
    left: import("./types").EmailVersion;
    right: import("./types").EmailVersion;
  }>;
}

export async function approveEmail(emailId: string) {
  const res = await fetch(`${API_URL}/emails/${emailId}/approve`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to approve email");
  return res.json();
}

export async function rejectEmail(emailId: string, reason?: string) {
  const res = await fetch(`${API_URL}/emails/${emailId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error("Failed to reject email");
  return res.json();
}

export async function sendEmail(emailId: string) {
  const res = await fetch(`${API_URL}/emails/${emailId}/send`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to send email");
  return res.json();
}

export async function editEmail(
  emailId: string,
  updates: {
    subject?: string;
    body?: string;
    resume_version_id?: string;
  }
) {
  const res = await fetch(`${API_URL}/emails/${emailId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error("Failed to edit email");
  return res.json();
}

export async function fetchPipeline() {
  const res = await fetch(`${API_URL}/pipeline`);
  if (!res.ok) throw new Error("Failed to fetch pipeline");
  return res.json();
}

export function createEventSource(onMessage: (event: MessageEvent) => void) {
  const es = new EventSource(buildApiUrl("/agent-events/stream"));
  es.onmessage = onMessage;
  return es;
}

export async function uploadResume(formData: FormData) {
  const res = await fetch(`${API_URL}/resumes/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload resume");
  return res.json();
}

export async function fetchResumes(userId: string) {
  const res = await fetch(`${API_URL}/resumes?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error("Failed to fetch resumes");
  return res.json();
}

export async function activateResume(resumeId: string, userId: string) {
  const res = await fetch(
    `${API_URL}/resumes/${resumeId}/activate?user_id=${encodeURIComponent(userId)}`,
    {
      method: "POST",
    }
  );
  if (!res.ok) throw new Error("Failed to activate resume");
  return res.json();
}

export async function deleteResume(resumeId: string, userId: string) {
  const res = await fetch(
    `${API_URL}/resumes/${resumeId}?user_id=${encodeURIComponent(userId)}`,
    {
      method: "DELETE",
    }
  );
  if (!res.ok) throw new Error("Failed to delete resume");
  return res.json();
}

// ─── Company Finder API ───────────────────────────────────────────────────────

export async function runCompanyFinder(payload: {
  user_id: string;
  resume_version_id?: string;
  preferences?: Record<string, unknown>;
  count?: number;
  rediscover?: boolean;
}) {
  const res = await fetch(`${API_URL}/company-finder/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to start company finder");
  return res.json() as Promise<{ task_id: string; status: string }>;
}

export async function discoverCompanies(payload: {
  user_id: string;
  preferences?: Record<string, unknown>;
  count?: number;
}) {
  const res = await fetch(`${API_URL}/company-finder/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to start company discovery");
  return res.json() as Promise<{ task_id: string; status: string }>;
}

export async function fetchDiscoveredCompanies(
  userId: string,
  opts?: {
    limit?: number;
    offset?: number;
    minScore?: number;
    includeArchived?: boolean;
    includeRemoved?: boolean;
    stage?: string;
    source?: string;
  }
) {
  const params = new URLSearchParams({ user_id: userId });
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.minScore != null) params.set("min_score", String(opts.minScore));
  if (opts?.includeArchived) params.set("include_archived", "true");
  if (opts?.includeRemoved) params.set("include_removed", "true");
  if (opts?.stage) params.set("stage", opts.stage);
  if (opts?.source) params.set("source", opts.source);
  const res = await fetch(`${API_URL}/company-finder/companies?${params}`);
  if (!res.ok) throw new Error("Failed to fetch companies");
  return res.json() as Promise<CompanyWorkspaceResponse>;
}

export async function repairCompanyWorkspace(userId: string) {
  const res = await fetch(`${API_URL}/company-finder/companies/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to start workspace repair");
  return res.json() as Promise<{ status: string; user_id: string }>;
}

export async function updateWorkspaceCompany(
  companyId: string,
  payload: {
    user_id: string;
    archived?: boolean;
    removed?: boolean;
    liked?: boolean;
    disliked?: boolean;
    notes?: string;
    orchestration_stage?: string;
    personalization_completed?: boolean;
    outreach_started?: boolean;
    outreach_sent?: boolean;
  }
) {
  const res = await fetch(`${API_URL}/company-finder/companies/${companyId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update company workspace state");
  return res.json();
}

export async function sendCompanyFeedback(
  companyId: string,
  payload: {
    user_id: string;
    feedback_type: "like" | "dislike";
    feedback_reason?: string;
  }
) {
  const res = await fetch(`${API_URL}/company-finder/companies/${companyId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save company feedback");
  return res.json();
}

export async function continueCompanyDiscovery(payload: {
  user_id: string;
  count?: number;
  source_mode?: string;
}) {
  const res = await fetch(`${API_URL}/company-finder/continue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to continue discovery");
  return res.json() as Promise<{ task_id: string; status: string }>;
}

export async function fetchDiscoverySessions(
  userId: string,
  opts?: { limit?: number; offset?: number }
) {
  const params = new URLSearchParams();
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  const res = await fetch(`${API_URL}/company-finder/discovery-sessions/${encodeURIComponent(userId)}?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch discovery sessions");
  return res.json() as Promise<{ sessions: import("./types").DiscoverySession[]; total: number }>;
}

export async function fetchDiscoverySourceLogs(
  userId: string,
  opts?: { sessionId?: string; limit?: number }
) {
  const params = new URLSearchParams();
  if (opts?.sessionId) params.set("session_id", opts.sessionId);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const res = await fetch(
    `${API_URL}/company-finder/source-logs/${encodeURIComponent(userId)}?${params.toString()}`
  );
  if (!res.ok) throw new Error("Failed to fetch source logs");
  return res.json() as Promise<{ logs: import("./types").DiscoverySourceLog[]; total: number }>;
}

export async function fetchOrchestrationState(userId: string) {
  const res = await fetch(`${API_URL}/company-finder/orchestration/${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error("Failed to fetch orchestration state");
  return res.json() as Promise<{ state: import("./types").OrchestrationState | null }>;
}

export async function saveOrchestrationState(
  userId: string,
  payload: {
    current_stage?: string;
    progress?: Record<string, unknown>;
    active_agents?: string[];
    paused_state?: boolean;
    last_task_id?: string;
  }
) {
  const res = await fetch(`${API_URL}/company-finder/orchestration/${encodeURIComponent(userId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to save orchestration state");
  return res.json() as Promise<{ state: import("./types").OrchestrationState }>;
}

export async function fetchCompanyDetail(companyId: string, userId?: string) {
  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_URL}/company-finder/companies/${companyId}${suffix}`);
  if (!res.ok) throw new Error("Failed to fetch company detail");
  return res.json() as Promise<{ company: import("./types").Company }>;
}

export async function addManualCompany(payload: {
  user_id: string;
  website_url: string;
}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90_000); // 90 s — scraping 4 pages at 15s each
  try {
    const res = await fetch(`${API_URL}/company-finder/companies/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      let detail = "Failed to add company";
      try {
        const data = await res.json();
        detail = data.detail || detail;
      } catch {
        // keep fallback message
      }
      throw new Error(detail);
    }
    return res.json() as Promise<{ company: import("./types").Company; task_id: string }>;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Request timed out. The site may be slow — try again.");
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      throw new Error("Could not reach the backend. Is the server running?");
    }
    throw err;
  }
}

export async function handoffToAgent(
  companyId: string,
  targetAgent: "email-writer" | "resume-tailor",
  userId: string
) {
  const params = new URLSearchParams({ target_agent: targetAgent, user_id: userId });
  const res = await fetchWithTimeout(
    `${API_URL}/company-finder/companies/${companyId}/handoff?${params}`,
    { method: "POST" },
    20_000
  );
  if (!res.ok) throw new Error("Failed to hand off to agent");
  return res.json() as Promise<{
    task_id: string;
    status: string;
    target_agent: string;
    company: string;
  }>;
}

export async function fetchParsedProfile(userId: string) {
  const res = await fetch(
    `${API_URL}/company-finder/profile/${encodeURIComponent(userId)}`
  );
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json() as Promise<{ profile: import("./types").ParsedProfile | null }>;
}

export async function parseResumeProfile(userId: string, resumeVersionId?: string) {
  const res = await fetch(`${API_URL}/company-finder/parse-resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, resume_version_id: resumeVersionId }),
  });
  if (!res.ok) throw new Error("Failed to parse resume");
  return res.json() as Promise<{ profile: import("./types").ParsedProfile }>;
}

export async function fetchUserPreferences(userId: string) {
  const res = await fetch(
    `${API_URL}/company-finder/preferences/${encodeURIComponent(userId)}`
  );
  if (!res.ok) throw new Error("Failed to fetch preferences");
  return res.json() as Promise<{ preferences: import("./types").UserPreferences | null }>;
}

export async function saveUserPreferences(
  userId: string,
  preferences: Partial<import("./types").UserPreferences>
) {
  const res = await fetch(`${API_URL}/company-finder/preferences`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, preferences }),
  });
  if (!res.ok) throw new Error("Failed to save preferences");
  return res.json();
}

export async function chatPreferences(payload: {
  user_id: string;
  message: string;
  history: Array<{ role: string; content: string }>;
  current_prefs?: Record<string, unknown>;
}) {
  const res = await fetch(`${API_URL}/company-finder/preferences/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to chat preferences");
  return res.json() as Promise<{
    reply: string;
    preferences: import("./types").UserPreferences | null;
    is_complete: boolean;
  }>;
}

export async function getPreferenceOpener(userId: string): Promise<string> {
  const res = await fetch(
    `${API_URL}/company-finder/preferences/opener?user_id=${encodeURIComponent(userId)}`
  );
  if (!res.ok) return "What types of roles are you targeting?";
  const data = await res.json();
  return data.message ?? "What types of roles are you targeting?";
}

export async function fetchConversationHistory(userId: string) {
  const res = await fetch(
    `${API_URL}/company-finder/conversation/${encodeURIComponent(userId)}`
  );
  if (!res.ok) return { history: [] };
  return res.json() as Promise<{ history: import("./types").ConversationMessage[] }>;
}

