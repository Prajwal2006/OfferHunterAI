"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Building2,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchDiscoveredCompanies,
  runCompanyFinder,
  handoffToAgent,
  addManualCompany,
  updateWorkspaceCompany,
  sendCompanyFeedback,
  continueCompanyDiscovery,
  fetchDiscoverySourceLogs,
  generateCoverLetter,
  generateResumeSuggestions,
  buildApiUrl,
} from "@/lib/api";
import {
  Company,
  UserPreferences,
  ConversationMessage,
  OrchestrationState,
  DiscoverySession,
  DiscoverySourceLog,
} from "@/lib/types";
import CompanyCard from "@/components/company-finder/CompanyCard";
import CompanyDetailModal from "@/components/company-finder/CompanyDetailModal";
import PreferenceWizard from "@/components/company-finder/PreferenceWizard";
import { createEventSource } from "@/lib/api";

// ─── Flow Steps ───────────────────────────────────────────────────────────────

type FlowStep =
  | "checking"   // Initial loading state
  | "no-resume"  // User has no resume
  | "preferences" // Collect preferences
  | "running"    // Agent running
  | "results"    // Show companies
  | "error";

// ─── Loading Skeleton ─────────────────────────────────────────────────────────

function CompanyCardSkeleton({ i }: { i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: i * 0.1 }}
      className="glass border border-border rounded-2xl p-5 space-y-3"
    >
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 bg-muted rounded-xl animate-pulse" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-muted rounded animate-pulse w-2/3" />
          <div className="h-3 bg-muted rounded animate-pulse w-1/2" />
        </div>
        <div className="h-10 w-12 bg-muted rounded-xl animate-pulse" />
      </div>
      <div className="h-8 bg-muted rounded animate-pulse" />
      <div className="flex gap-1">
        {[1, 2, 3].map((k) => (
          <div key={k} className="h-5 w-16 bg-muted rounded-md animate-pulse" />
        ))}
      </div>
    </motion.div>
  );
}

// ─── Agent Status Banner ──────────────────────────────────────────────────────

function AgentStatusBanner({
  message,
  onCancel,
}: {
  message: string;
  onCancel?: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 px-4 py-3 bg-primary/10 border border-primary/25 rounded-xl text-sm"
    >
      <Loader2 className="w-4 h-4 text-primary animate-spin shrink-0" />
      <span className="flex-1 text-foreground">{message}</span>
      {onCancel && (
        <button
          onClick={onCancel}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </motion.div>
  );
}

// ─── Filter Bar ───────────────────────────────────────────────────────────────

interface Filters {
  search: string;
  industry: string;
  hiring: string;
  remote: string;
  minScore: number;
}

function companyMemoryKey(company: Company): string {
  return String(
    company.id ||
      company.domain?.toLowerCase().trim() ||
      company.website_url?.toLowerCase().trim() ||
      company.name?.toLowerCase().trim() ||
      ""
  );
}

function mergeCompanies(existing: Company[], incoming: Company[]): Company[] {
  const merged = new Map<string, Company>();
  for (const company of [...existing, ...incoming]) {
    const key = companyMemoryKey(company);
    if (!key) continue;
    merged.set(key, { ...(merged.get(key) || {}), ...company });
  }
  return Array.from(merged.values());
}

type StreamedAgentEvent = {
  type?: string;
  task_id?: string;
  agent_name?: string;
  status?: "started" | "running" | "completed" | "failed";
  message?: string;
  metadata?: Record<string, unknown>;
};

type SourcePipelineBreakdown = {
  raw_discovered: number;
  duplicates_removed: number;
  already_seen_filtered: number;
  ranking_filtered: number;
  persistence_failed: number;
  persisted: number;
};

function getPipelineBreakdown(log: DiscoverySourceLog): SourcePipelineBreakdown | null {
  const metadata = log.metadata || {};
  const raw = Number((metadata as Record<string, unknown>).raw_discovered);
  const duplicates = Number((metadata as Record<string, unknown>).duplicates_removed);
  const alreadySeen = Number((metadata as Record<string, unknown>).already_seen_filtered);
  const rankingFiltered = Number((metadata as Record<string, unknown>).ranking_filtered);
  const failed = Number((metadata as Record<string, unknown>).persistence_failed);
  const persisted = Number((metadata as Record<string, unknown>).persisted);

  if ([raw, duplicates, alreadySeen, rankingFiltered, failed, persisted].every((v) => Number.isNaN(v))) {
    return null;
  }

  return {
    raw_discovered: Number.isFinite(raw) ? raw : 0,
    duplicates_removed: Number.isFinite(duplicates) ? duplicates : 0,
    already_seen_filtered: Number.isFinite(alreadySeen) ? alreadySeen : 0,
    ranking_filtered: Number.isFinite(rankingFiltered) ? rankingFiltered : 0,
    persistence_failed: Number.isFinite(failed) ? failed : 0,
    persisted: Number.isFinite(persisted) ? persisted : Number(log.result_count || 0),
  };
}

function stageLabel(stage: string): string {
  const normalized = stage.trim().toLowerCase();
  const labels: Record<string, string> = {
    resume_parse: "Parsing your resume",
    query_expansion: "Building smart search queries",
    company_discovery: "Searching across company sources",
    enrichment: "Enriching company intelligence",
    ranking: "Ranking companies for your profile",
    contact_discovery: "Finding recruiter and founder contacts",
    persistence: "Saving results to your workspace",
    embeddings: "Generating semantic embeddings",
    background_hydration: "Hydrating company intelligence in background",
  };
  return labels[normalized] || "Processing";
}

function inferStageFromEvent(data: StreamedAgentEvent): string {
  const metadata = data.metadata || {};
  const fromMetadata = String(metadata.stage || "").trim();
  if (fromMetadata) return fromMetadata;

  const source = String(metadata.source || "").trim().toLowerCase();
  if (source === "queryexpansion") return "query_expansion";
  if (source) return "company_discovery";

  const message = String(data.message || "").toLowerCase();
  if (message.includes("resume")) return "resume_parse";
  if (message.includes("expanding search queries") || message.includes("query")) return "query_expansion";
  if (message.includes("enrich")) return "enrichment";
  if (message.includes("ranking") || message.includes("ranked:")) return "ranking";
  if (message.includes("contact")) return "contact_discovery";
  if (message.includes("saving") || message.includes("persist")) return "persistence";
  return "company_discovery";
}

function buildAgentBannerMessage(data: StreamedAgentEvent): string {
  const stage = inferStageFromEvent(data);
  const label = stageLabel(stage);
  const metadata = data.metadata || {};
  const source = String(metadata.source || "").trim();
  const status = data.status || "running";

  if (stage === "company_discovery" && source && source !== "QueryExpansion") {
    return `${label}: ${source}...`;
  }

  if (status === "completed") {
    return "Discovery complete. Finalizing results...";
  }

  return `${label}...`;
}

function FilterBar({
  filters,
  onChange,
  industries,
}: {
  filters: Filters;
  onChange: (f: Partial<Filters>) => void;
  industries: string[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Search */}
      <div className="relative flex-1 min-w-48">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search companies..."
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          className="w-full pl-9 pr-3 py-2 bg-muted border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors"
        />
      </div>

      {/* Industry filter */}
      {industries.length > 1 && (
        <select
          value={filters.industry}
          onChange={(e) => onChange({ industry: e.target.value })}
          className="px-3 py-2 bg-muted border border-border rounded-xl text-sm text-foreground focus:border-primary focus:outline-none transition-colors"
        >
          <option value="">All Industries</option>
          {industries.map((ind) => (
            <option key={ind} value={ind}>
              {ind}
            </option>
          ))}
        </select>
      )}

      {/* Hiring status */}
      <select
        value={filters.hiring}
        onChange={(e) => onChange({ hiring: e.target.value })}
        className="px-3 py-2 bg-muted border border-border rounded-xl text-sm text-foreground focus:border-primary focus:outline-none transition-colors"
      >
        <option value="">Any Status</option>
        <option value="actively_hiring">Actively Hiring</option>
        <option value="hiring">Hiring</option>
      </select>

      {/* Remote filter */}
      <select
        value={filters.remote}
        onChange={(e) => onChange({ remote: e.target.value })}
        className="px-3 py-2 bg-muted border border-border rounded-xl text-sm text-foreground focus:border-primary focus:outline-none transition-colors"
      >
        <option value="">Any Location</option>
        <option value="remote">Remote</option>
        <option value="onsite">Onsite</option>
      </select>

      {/* Min score */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <SlidersHorizontal className="w-4 h-4" />
        <span>Min {Math.round(filters.minScore * 100)}%</span>
        <input
          type="range"
          min={0}
          max={0.9}
          step={0.1}
          value={filters.minScore}
          onChange={(e) => onChange({ minScore: Number(e.target.value) })}
          className="w-20 accent-primary"
        />
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

function CompanyFinderContent() {
  const { session } = useAuth();
  const userId = session?.user?.id ?? "";

  const [step, setStep] = useState<FlowStep>("checking");
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [agentMessage, setAgentMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [prefOpener, setPrefOpener] = useState("");
  const [prefHistory, setPrefHistory] = useState<ConversationMessage[]>([]);
  const [filters, setFilters] = useState<Filters>({
    search: "",
    industry: "",
    hiring: "",
    remote: "",
    minScore: 0,
  });
  const [showPrefsPane, setShowPrefsPane] = useState(false);
  const [manualWebsiteUrl, setManualWebsiteUrl] = useState("");
  const [manualCompanyError, setManualCompanyError] = useState<string | null>(null);
  const [manualCompanyLoading, setManualCompanyLoading] = useState(false);
  const [orchestrationState, setOrchestrationState] = useState<OrchestrationState | null>(null);
  const [discoverySessions, setDiscoverySessions] = useState<DiscoverySession[]>([]);
  const [sourceLogs, setSourceLogs] = useState<DiscoverySourceLog[]>([]);
  const [sourceMode, setSourceMode] = useState<string>("all");
  const [initAttempt, setInitAttempt] = useState(0);
  const esRef = useRef<EventSource | null>(null);
  const activeTaskIdRef = useRef<string | null>(null);
  const currentStageRef = useRef<string>("company_discovery");
  // Initialized in a mount effect (Date.now() is impure, so it must not run
  // during render); always re-stamped when a discovery run starts.
  const stageStartedAtRef = useRef<number>(0);
  const repairRequestedForUserRef = useRef<string | null>(null);
  // Track whether the running state was triggered by "Find More" (merge) vs fresh
  // run (replace). State (not a ref) so the skeleton-vs-merge render stays in sync.
  const [isContinuing, setIsContinuing] = useState(false);

  // Stamp the stage timer once on mount (kept out of render for purity).
  useEffect(() => {
    stageStartedAtRef.current = Date.now();
  }, []);

  // ── Initial load ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const activeControllers = new Set<AbortController>();
    const FETCH_TIMEOUT_MS = 15_000;

    // Wraps fetch with a per-call timeout so a slow/hung API never blocks "checking" forever.
    async function fetchWithTimeout(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
      const controller = new AbortController();
      activeControllers.add(controller);
      const timeoutId = setTimeout(() => controller.abort("timeout"), FETCH_TIMEOUT_MS);

      try {
        return await fetch(input, { ...init, signal: controller.signal });
      } catch (err) {
        if (controller.signal.aborted && controller.signal.reason === "timeout") {
          throw new Error("Request timed out");
        }
        throw err;
      } finally {
        clearTimeout(timeoutId);
        activeControllers.delete(controller);
      }
    }

    async function fetchJsonWithTimeout<T>(
      input: RequestInfo | URL,
      init?: RequestInit,
      fallback?: T
    ): Promise<T> {
      try {
        const response = await fetchWithTimeout(input, init);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        return (await response.json()) as T;
      } catch (err) {
        if (fallback !== undefined) {
          return fallback;
        }
        throw err;
      }
    }

    function isCleanupAbortError(err: unknown): boolean {
      return (
        err instanceof DOMException && err.name === "AbortError"
      ) || (err instanceof Error && /aborted|aborterror/i.test(err.message));
    }

    async function init() {
      try {
        setError(null);
        setAgentMessage("");

        // 1. Check for resume
        const resumeRes = await fetchWithTimeout(
          buildApiUrl(`/resumes?user_id=${encodeURIComponent(userId)}`)
        );
        if (cancelled) return;
        if (!resumeRes.ok) throw new Error("Failed to fetch resumes");
        const resumeData = await resumeRes.json();
        if (cancelled) return;
        const resumes = resumeData.resumes ?? [];

        if (resumes.length === 0) {
          setStep("no-resume");
          return;
        }

        // 2. Check for parsed profile (result ignored — just ensures it exists)
        await fetchWithTimeout(
          buildApiUrl(`/company-finder/profile/${encodeURIComponent(userId)}`)
        ).catch(() => null);
        if (cancelled) return;

        // 3. Check for preferences
        const prefsRes = await fetchWithTimeout(
          buildApiUrl(`/company-finder/preferences/${encodeURIComponent(userId)}`)
        );
        if (cancelled) return;
        if (!prefsRes.ok) throw new Error("Failed to fetch preferences");
        const prefsData = await prefsRes.json();
        if (cancelled) return;
        setPreferences(prefsData.preferences);

        const [orchestration, sessions, logs] = await Promise.all([
          fetchJsonWithTimeout<{ state: OrchestrationState | null }>(
            buildApiUrl(`/company-finder/orchestration/${encodeURIComponent(userId)}`),
            undefined,
            { state: null }
          ),
          fetchJsonWithTimeout<{ sessions: DiscoverySession[] }>(
            buildApiUrl(`/company-finder/discovery-sessions/${encodeURIComponent(userId)}?limit=8`),
            undefined,
            { sessions: [] }
          ),
          fetchJsonWithTimeout<{ logs: DiscoverySourceLog[] }>(
            buildApiUrl(`/company-finder/source-logs/${encodeURIComponent(userId)}?limit=24`),
            undefined,
            { logs: [] }
          ),
        ]);
        if (cancelled) return;
        setOrchestrationState(orchestration.state ?? null);
        setDiscoverySessions(sessions.sessions ?? []);
        setSourceLogs(logs.logs ?? []);

        if (!prefsData.preferences?.conversation_complete) {
          // Need to collect preferences
          const [opener, histData] = await Promise.all([
            fetchJsonWithTimeout<{ message: string }>(
              buildApiUrl(`/company-finder/preferences/opener?user_id=${encodeURIComponent(userId)}`),
              undefined,
              { message: "What kinds of roles are you targeting?" }
            ),
            fetchJsonWithTimeout<{ history: ConversationMessage[] }>(
              buildApiUrl(`/company-finder/conversation/${encodeURIComponent(userId)}`),
              undefined,
              { history: [] }
            ),
          ]);
          if (cancelled) return;
          setPrefOpener(opener.message ?? "What kinds of roles are you targeting?");
          setPrefHistory(histData.history ?? []);
          setStep("preferences");
          return;
        }

        // 4. Check for existing companies — show them without auto-running discovery
        const companyData = await fetchJsonWithTimeout<{ companies: Company[] }>(
          buildApiUrl(`/company-finder/companies?user_id=${encodeURIComponent(userId)}&limit=1000`),
          undefined,
          { companies: [] }
        );
        if (cancelled) return;
        setCompanies((prev) => mergeCompanies(prev, companyData.companies));
        setStep("results");
        if (repairRequestedForUserRef.current !== userId) {
          repairRequestedForUserRef.current = userId;
          void fetchJsonWithTimeout<{ status: string; user_id: string }>(
            buildApiUrl("/company-finder/companies/repair"),
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ user_id: userId }),
            },
            { status: "skipped", user_id: userId }
          )
            .then(() => new Promise((resolve) => setTimeout(resolve, 2500)))
            .then(() =>
              fetchJsonWithTimeout<{ companies: Company[] }>(
                buildApiUrl(`/company-finder/companies?user_id=${encodeURIComponent(userId)}&limit=1000`),
                undefined,
                { companies: [] }
              )
            )
            .then((data) => {
              if (!cancelled) {
                setCompanies((prev) => mergeCompanies(prev, data.companies));
              }
            })
            .catch(() => {
              // Workspace repair is best-effort and must never block page load.
            });
        }
      } catch (err) {
        if (cancelled) return;
        if (isCleanupAbortError(err)) return;
        setError(err instanceof Error ? err.message : "Initialization failed");
        setStep("error");
      }
    }

    init();
    return () => {
      cancelled = true;
      for (const controller of activeControllers) {
        controller.abort("cleanup");
      }
    };
  }, [userId, initAttempt]);

  // ── SSE Event Stream for agent progress ────────────────────────────────────
  useEffect(() => {
    if (step !== "running") {
      esRef.current?.close();
      return;
    }

    esRef.current?.close();
    const es = createEventSource((event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as StreamedAgentEvent;
        if (data.type === "connected") return;
        if (activeTaskIdRef.current && data.task_id !== activeTaskIdRef.current) return;
        if (data.agent_name === "CompanyFinderAgent" || data.agent_name === "Orchestrator") {
          const stage = inferStageFromEvent(data);
          if (stage !== currentStageRef.current) {
            currentStageRef.current = stage;
            stageStartedAtRef.current = Date.now();
          }
          setAgentMessage(buildAgentBannerMessage(data));

          const shouldRefreshCompanies = Boolean((data.metadata || {}).refresh_companies);
          if (shouldRefreshCompanies) {
            fetchDiscoveredCompanies(userId, { limit: 1000 })
              .then((res) => {
                setCompanies((prev) => mergeCompanies(prev, res.companies));
                void fetchDiscoverySourceLogs(userId, { limit: 24 }).then((logs) =>
                  setSourceLogs(logs.logs ?? [])
                );
              })
              .catch(() => {
                // best-effort refresh only
              });
          }

          if (data.status === "completed") {
            setIsContinuing(false);
            // Always reload from DB so persisted state is the source of truth
            fetchDiscoveredCompanies(userId, { limit: 1000 })
              .then((res) => {
                setCompanies((prev) =>
                  res.companies.length > 0 || prev.length === 0
                    ? mergeCompanies(prev, res.companies)
                    : prev
                );
                activeTaskIdRef.current = null;
                setStep("results");
                void fetchDiscoverySourceLogs(userId, { limit: 24 }).then((logs) =>
                  setSourceLogs(logs.logs ?? [])
                );
              })
              .catch(() => {
                activeTaskIdRef.current = null;
                setStep("results");
              });
          } else if (data.status === "failed") {
            setIsContinuing(false);
            setError(data.message || "Agent failed");
            activeTaskIdRef.current = null;
            setStep("error");
          }
        }
      } catch {
        // ignore malformed events
      }
    });
    esRef.current = es;

    // Fallback: if the SSE completion event is missed (e.g. connection gap), poll
    // for companies after 4 minutes and exit the running state regardless.
    const fallbackTimer = setTimeout(() => {
      setIsContinuing(false);
      fetchDiscoveredCompanies(userId, { limit: 1000 })
        .then((res) => {
          setCompanies((prev) => mergeCompanies(prev, res.companies));
          activeTaskIdRef.current = null;
          setStep("results");
        })
        .catch(() => {
          activeTaskIdRef.current = null;
          setStep("results");
        });
    }, 4 * 60 * 1000);

    const stagePulseTimer = setInterval(() => {
      const elapsedSeconds = Math.max(1, Math.round((Date.now() - stageStartedAtRef.current) / 1000));
      setAgentMessage(`${stageLabel(currentStageRef.current)}... ${elapsedSeconds}s`);
    }, 5000);

    return () => {
      es.close();
      clearTimeout(fallbackTimer);
      clearInterval(stagePulseTimer);
    };
  }, [step, userId]);

  // ── Start discovery ────────────────────────────────────────────────────────
  const startDiscovery = useCallback(async (rediscover = false) => {
    setStep("running");
    currentStageRef.current = "company_discovery";
    stageStartedAtRef.current = Date.now();
    setAgentMessage("Preparing discovery run...");
    setError(null);
    try {
      const result = await runCompanyFinder({ user_id: userId, count: 60, rediscover });
      activeTaskIdRef.current = result.task_id;
    } catch (err) {
      activeTaskIdRef.current = null;
      setError(err instanceof Error ? err.message : "Failed to start agent");
      setStep("error");
    }
  }, [userId]);

  // ── On preference completion ───────────────────────────────────────────────
  const onPreferencesComplete = useCallback(
    async (prefs: UserPreferences) => {
      setPreferences(prefs);
      await startDiscovery(false);
    },
    [startDiscovery]
  );

  // ── Handoff ────────────────────────────────────────────────────────────────
  const onHandoff = useCallback(
    async (
      companyId: string,
      agent: "email-writer" | "resume-tailor" | "personalizer"
    ) => {
      try {
        await handoffToAgent(companyId, agent, userId);
      } catch {
        // silently fail for now
      }
    },
    [userId]
  );

  const onGenerateCoverLetter = useCallback(
    async (companyId: string) => {
      const { result } = await generateCoverLetter(companyId, { user_id: userId });
      return result;
    },
    [userId]
  );

  const onGenerateResumeSuggestions = useCallback(
    async (companyId: string) => {
      const { result } = await generateResumeSuggestions(companyId, { user_id: userId });
      return result;
    },
    [userId]
  );

  const onAddManualCompany = useCallback(async () => {
    const websiteUrl = manualWebsiteUrl.trim();
    if (!websiteUrl) return;

    setManualCompanyLoading(true);
    setManualCompanyError(null);
    try {
      const result = await addManualCompany({ user_id: userId, website_url: websiteUrl });
      setCompanies((prev) => {
        const newId = result.company.id;
        const newDomain = (result.company.domain || "").toLowerCase();
        const deduped = prev.filter(
          (company) => {
            const sameId = Boolean(newId) && Boolean(company.id) && company.id === newId;
            const sameDomain =
              Boolean(newDomain) &&
              Boolean(company.domain) &&
              company.domain.toLowerCase() === newDomain;
            return !sameId && !sameDomain;
          }
        );
        return [result.company, ...deduped];
      });
      setManualWebsiteUrl("");
      setSelectedCompany(result.company);
      setStep("results");
    } catch (err) {
      setManualCompanyError(err instanceof Error ? err.message : "Failed to add company");
    } finally {
      setManualCompanyLoading(false);
    }
  }, [manualWebsiteUrl, userId]);

  const onCompanyFeedback = useCallback(
    async (company: Company, feedback: "like" | "dislike") => {
      if (!company.id) return;
      const nextLiked = feedback === "like";
      const nextDisliked = feedback === "dislike";

      setCompanies((prev) =>
        prev.map((c) =>
          c.id === company.id
            ? {
                ...c,
                workspace: {
                  ...(c.workspace || {}),
                  liked: nextLiked,
                  disliked: nextDisliked,
                },
              }
            : c
        )
      );

      try {
        await sendCompanyFeedback(company.id, {
          user_id: userId,
          feedback_type: feedback,
        });
      } catch {
        await fetchDiscoveredCompanies(userId, { limit: 1000 }).then((data) =>
          setCompanies((prev) => mergeCompanies(prev, data.companies))
        );
      }
    },
    [userId]
  );

  const onArchiveCompany = useCallback(
    async (company: Company) => {
      if (!company.id) return;
      setCompanies((prev) => prev.filter((c) => c.id !== company.id));
      try {
        await updateWorkspaceCompany(company.id, { user_id: userId, archived: true });
      } catch {
        await fetchDiscoveredCompanies(userId, { limit: 1000 }).then((data) =>
          setCompanies((prev) => mergeCompanies(prev, data.companies))
        );
      }
    },
    [userId]
  );

  const onRemoveCompany = useCallback(
    async (company: Company) => {
      if (!company.id) return;
      setCompanies((prev) => prev.filter((c) => c.id !== company.id));
      try {
        await updateWorkspaceCompany(company.id, { user_id: userId, removed: true });
      } catch {
        await fetchDiscoveredCompanies(userId, { limit: 1000 }).then((data) =>
          setCompanies((prev) => mergeCompanies(prev, data.companies))
        );
      }
    },
    [userId]
  );

  const onFindMoreCompanies = useCallback(async () => {
    setIsContinuing(true);
    setStep("running");
    currentStageRef.current = "company_discovery";
    stageStartedAtRef.current = Date.now();
    setAgentMessage("Continuing discovery and expanding your workspace...");
    setError(null);
    try {
      const result = await continueCompanyDiscovery({
        user_id: userId,
        count: 40,
        source_mode: sourceMode === "all" ? undefined : sourceMode,
      });
      activeTaskIdRef.current = result.task_id;
    } catch (err) {
      setIsContinuing(false);
      activeTaskIdRef.current = null;
      setError(err instanceof Error ? err.message : "Failed to continue discovery");
      setStep("results"); // Stay on results so existing companies remain visible
    }
  }, [sourceMode, userId]);

  // ── Filter companies ───────────────────────────────────────────────────────
  const filteredCompanies = companies.filter((c) => {
    if (filters.search) {
      const q = filters.search.toLowerCase();
      if (
        !c.name.toLowerCase().includes(q) &&
        !(c.industry || "").toLowerCase().includes(q) &&
        !(c.description || "").toLowerCase().includes(q)
      ) {
        return false;
      }
    }
    if (filters.industry && c.industry !== filters.industry) return false;
    if (filters.hiring && c.hiring_status !== filters.hiring) return false;
    if (filters.remote === "remote" && !c.remote_friendly) return false;
    if (filters.remote === "onsite" && c.remote_friendly) return false;
    const score = c.ranking?.match_score ?? c.match_score ?? c.relevance_score ?? 0;
    if (score < filters.minScore) return false;
    return true;
  });

  const industries = [...new Set(companies.map((c) => c.industry).filter(Boolean))] as string[];

  // ── Render ─────────────────────────────────────────────────────────────────

  if (step === "checking") {
    return (
      <div className="flex flex-col items-center justify-center min-h-96 gap-4">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
        <p className="text-muted-foreground text-sm">Checking your profile...</p>
      </div>
    );
  }

  if (step === "no-resume") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-lg mx-auto text-center py-16 px-4"
      >
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-bold text-foreground mb-2">
          Upload Your Resume First
        </h2>
        <p className="text-muted-foreground text-sm mb-6">
          The Company Finder Agent needs your resume to intelligently discover
          companies that match your skills, experience, and preferences.
        </p>
        <a
          href="/resume"
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition-colors"
        >
          Go to Resume Manager
          <ArrowRight className="w-4 h-4" />
        </a>
      </motion.div>
    );
  }

  if (step === "error") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-lg mx-auto text-center py-16 px-4"
      >
        <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-8 h-8 text-destructive" />
        </div>
        <h2 className="text-xl font-bold text-foreground mb-2">Something Went Wrong</h2>
        <p className="text-muted-foreground text-sm mb-6">{error}</p>
        <button
          onClick={() => {
            setError(null);
            setStep("checking");
            setInitAttempt((value) => value + 1);
          }}
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Try Again
        </button>
      </motion.div>
    );
  }

  if (step === "preferences") {
    return (
      <div className="max-w-2xl mx-auto h-[calc(100vh-200px)] min-h-125 flex flex-col">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 flex items-center gap-3"
        >
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">Tell Me About Your Goals</h2>
            <p className="text-xs text-muted-foreground">
              I&apos;ll use your answers to find perfectly matched companies
            </p>
          </div>
        </motion.div>

        <div className="flex-1 glass border border-border rounded-2xl overflow-hidden">
          <PreferenceWizard
            userId={userId}
            initialMessage={prefOpener}
            initialHistory={prefHistory}
            currentPrefs={preferences ?? undefined}
            onComplete={onPreferencesComplete}
          />
        </div>
      </div>
    );
  }

  if (step === "running" && !isContinuing && companies.length === 0) {
    // Fresh discovery with no existing results — show full skeleton screen
    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-primary animate-pulse" />
          </div>
          <h2 className="text-xl font-bold text-foreground mb-1">
            Discovering Companies For You
          </h2>
          <p className="text-sm text-muted-foreground">
            Scanning HackerNews, RemoteOK, Work at a Startup, Wellfound, YCombinator, and more...
          </p>
        </motion.div>

        {agentMessage && <AgentStatusBanner message={agentMessage} />}

        <div className="grid sm:grid-cols-2 gap-4 mt-8">
          {[...Array(6)].map((_, i) => (
            <CompanyCardSkeleton key={i} i={i} />
          ))}
        </div>
      </div>
    );
  }

  // ── Results (also shown during "running" when continuing with existing companies) ──
  return (
    <div className="space-y-6">
      {/* Running banner — shown when "Find More" is active so results stay visible */}
      {step === "running" && agentMessage && (
        <AgentStatusBanner
          message={agentMessage}
          onCancel={() => {
            setIsContinuing(false);
            activeTaskIdRef.current = null;
            setStep("results");
          }}
        />
      )}

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between flex-wrap gap-4"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Company Finder</h1>
            <p className="text-xs text-muted-foreground">
              {companies.length} companies discovered for you (progressively hydrated)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPrefsPane((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-colors ${
              showPrefsPane
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border hover:bg-muted text-muted-foreground"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            {preferences?.conversation_complete ? "Edit Preferences" : "Set Preferences"}
          </button>
          <button
            onClick={() => void startDiscovery(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-border hover:bg-muted text-sm text-muted-foreground transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Rediscover
          </button>
        </div>
      </motion.div>

      {/* Preference pane inline */}
      <AnimatePresence>
        {showPrefsPane && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "500px" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="h-125 glass border border-border rounded-2xl overflow-hidden">
              <PreferenceWizard
                userId={userId}
                initialMessage={prefOpener || "What types of roles are you targeting?"}
                initialHistory={prefHistory}
                currentPrefs={preferences ?? undefined}
                onComplete={(prefs) => {
                  setPreferences(prefs);
                  setShowPrefsPane(false);
                  startDiscovery(false);
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="glass border border-border rounded-2xl p-4 sm:p-5 space-y-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold text-foreground">Add A Company Yourself</h3>
          <p className="text-xs text-muted-foreground max-w-3xl">
            Paste a company homepage or careers URL. The bot will scrape the site, build a company profile,
            rank it against your resume and preferences, and make it available for email drafting like any
            discovered company.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="url"
            value={manualWebsiteUrl}
            onChange={(e) => setManualWebsiteUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void onAddManualCompany();
              }
            }}
            placeholder="https://company.com or https://company.com/careers"
            className="flex-1 px-4 py-2.5 bg-muted border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors"
          />
          <button
            type="button"
            onClick={() => void onAddManualCompany()}
            disabled={!manualWebsiteUrl.trim() || manualCompanyLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {manualCompanyLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Scraping...
              </>
            ) : (
              <>
                <Building2 className="w-4 h-4" />
                Add Company
              </>
            )}
          </button>
        </div>
        {manualCompanyError && (
          <p className="text-xs text-destructive">{manualCompanyError}</p>
        )}
      </div>

      {/* Filter bar */}
      <FilterBar
        filters={filters}
        onChange={(f) => setFilters((prev) => ({ ...prev, ...f }))}
        industries={industries}
      />

      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing{" "}
          <span className="font-medium text-foreground">{filteredCompanies.length}</span>{" "}
          of {companies.length} companies
        </span>
        {preferences?.conversation_complete && (
          <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Personalized for you
          </span>
        )}
      </div>

      <div className="glass border border-border rounded-2xl p-4 sm:p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Persistent Discovery Workspace</p>
            <p className="text-xs text-muted-foreground">
              Companies are saved to your account with orchestration state, feedback, and history.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            Stage: <span className="text-foreground font-medium">{orchestrationState?.current_stage || "CompanyFinder"}</span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={() => void onFindMoreCompanies()}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Find More Companies
          </button>

          <div className="flex items-center gap-2">
            <select
              value={sourceMode}
              onChange={(e) => setSourceMode(e.target.value)}
              className="px-3 py-2.5 bg-muted border border-border rounded-xl text-sm text-foreground focus:border-primary focus:outline-none transition-colors"
            >
              <option value="all">All Sources</option>
              <option value="startups">Startups</option>
              <option value="yc">YC Companies</option>
              <option value="remote">Remote Companies</option>
              <option value="ai">AI Startups</option>
              <option value="fortune500">Fortune 500</option>
              <option value="stealth">Stealth Startups</option>
              <option value="international">Hiring Internationally</option>
              <option value="visa">Visa-Sponsoring Companies</option>
            </select>
            <button
              type="button"
              onClick={() => void onFindMoreCompanies()}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              Search Different Sources
            </button>
          </div>
        </div>

        {discoverySessions.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Last session: {discoverySessions[0].companies_found || discoverySessions[0].total_companies_found || 0} companies,
            sources {Array.isArray(discoverySessions[0].sources_used) ? discoverySessions[0].sources_used.join(", ") : "n/a"}
          </p>
        )}

        {sourceLogs.length > 0 && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 pt-2">
            {sourceLogs.slice(0, 6).map((log) => (
              <div key={log.id} className="rounded-xl border border-border bg-muted/30 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-foreground truncate">{log.source}</span>
                  <span
                    className={
                      log.status === "success"
                        ? "text-green-600 dark:text-green-400"
                        : log.status === "timeout"
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-red-600 dark:text-red-400"
                    }
                  >
                    {log.status}
                  </span>
                </div>
                {(() => {
                  const breakdown = getPipelineBreakdown(log);
                  if (!breakdown) {
                    return (
                      <div className="mt-1 text-muted-foreground">
                        {log.result_count || 0} companies
                        {log.duration_ms ? ` · ${Math.round(log.duration_ms / 1000)}s` : ""}
                      </div>
                    );
                  }

                  return (
                    <div className="mt-1 text-muted-foreground space-y-0.5">
                      <div>
                        raw {breakdown.raw_discovered} · dedupe -{breakdown.duplicates_removed} · already known -{breakdown.already_seen_filtered}
                      </div>
                      <div>
                        filtered -{breakdown.ranking_filtered} · persist failed -{breakdown.persistence_failed} · visible {breakdown.persisted}
                      </div>
                      {log.duration_ms ? <div>{Math.round(log.duration_ms / 1000)}s</div> : null}
                    </div>
                  );
                })()}
                {log.error && (
                  <div className="mt-1 truncate text-red-600 dark:text-red-400">
                    {log.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Company Grid */}
      {companies.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <Building2 className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-30" />
          <p className="text-muted-foreground font-medium mb-1">No companies discovered yet.</p>
          <p className="text-sm text-muted-foreground mb-4">
            Click <span className="text-foreground font-medium">Find More Companies</span> above to start discovery.
          </p>
        </motion.div>
      ) : filteredCompanies.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <Building2 className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-30" />
          <p className="text-muted-foreground">No companies match your filters.</p>
          <button
            onClick={() =>
              setFilters({ search: "", industry: "", hiring: "", remote: "", minScore: 0 })
            }
            className="mt-3 text-primary text-sm hover:underline"
          >
            Clear filters
          </button>
        </motion.div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredCompanies.map((company, i) => (
              <CompanyCard
                key={company.id ?? company.name}
                company={company}
                index={i}
                onClick={setSelectedCompany}
                onFeedback={onCompanyFeedback}
                onArchive={onArchiveCompany}
                onRemove={onRemoveCompany}
              />
            ))}
          </div>

          {/* Bottom Find More Companies button */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2 pb-4">
            <button
              type="button"
              onClick={() => void onFindMoreCompanies()}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Find More Companies
            </button>
            <button
              type="button"
              onClick={() => void onFindMoreCompanies()}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              Search Different Sources
            </button>
          </div>
        </>
      )}

      {/* Company Detail Modal */}
      <AnimatePresence>
        {selectedCompany && (
          <CompanyDetailModal
            company={selectedCompany}
            onClose={() => setSelectedCompany(null)}
            onHandoff={onHandoff}
            onGenerateCoverLetter={onGenerateCoverLetter}
            onGenerateResumeSuggestions={onGenerateResumeSuggestions}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default function CompanyFinderPage() {
  return (
    <RequireAuth>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <CompanyFinderContent />
      </div>
    </RequireAuth>
  );
}
