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
