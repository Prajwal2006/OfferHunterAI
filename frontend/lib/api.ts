const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchAgentEvents(limit = 50) {
  const res = await fetch(`${API_URL}/agent-events?limit=${limit}`);
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
  const es = new EventSource(`${API_URL}/agent-events/stream`);
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
  opts?: { limit?: number; minScore?: number }
) {
  const params = new URLSearchParams({ user_id: userId });
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.minScore != null) params.set("min_score", String(opts.minScore));
  const res = await fetch(`${API_URL}/company-finder/companies?${params}`);
  if (!res.ok) throw new Error("Failed to fetch companies");
  return res.json() as Promise<{ companies: import("./types").Company[]; total: number }>;
}

export async function fetchCompanyDetail(companyId: string) {
  const res = await fetch(`${API_URL}/company-finder/companies/${companyId}`);
  if (!res.ok) throw new Error("Failed to fetch company detail");
  return res.json() as Promise<{ company: import("./types").Company }>;
}

export async function handoffToAgent(
  companyId: string,
  targetAgent: string,
  userId: string
) {
  const params = new URLSearchParams({ target_agent: targetAgent, user_id: userId });
  const res = await fetch(
    `${API_URL}/company-finder/companies/${companyId}/handoff?${params}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Failed to hand off to agent");
  return res.json();
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

