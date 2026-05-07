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
  fetchParsedProfile,
  fetchUserPreferences,
  getPreferenceOpener,
  fetchConversationHistory,
  runCompanyFinder,
  fetchResumes,
  handoffToAgent,
  addManualCompany,
  updateWorkspaceCompany,
  sendCompanyFeedback,
  continueCompanyDiscovery,
  fetchOrchestrationState,
  fetchDiscoverySessions,
} from "@/lib/api";
import {
  Company,
  UserPreferences,
  ConversationMessage,
  OrchestrationState,
  DiscoverySession,
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
  const [sourceMode, setSourceMode] = useState<string>("all");
  const esRef = useRef<EventSource | null>(null);
  // Track whether the running state was triggered by "Find More" (merge) vs fresh run (replace)
  const isContinuingRef = useRef(false);

  // ── Initial load ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!userId) return;

    async function init() {
      try {
        // 1. Check for resume
        const resumeData = await fetchResumes(userId);
        const resumes = resumeData.resumes ?? [];

        if (resumes.length === 0) {
          setStep("no-resume");
          return;
        }

        // 2. Check for parsed profile
        await fetchParsedProfile(userId);

        // 3. Check for preferences
        const prefsData = await fetchUserPreferences(userId);
        setPreferences(prefsData.preferences);

        const [orchestration, sessions] = await Promise.all([
          fetchOrchestrationState(userId).catch(() => ({ state: null })),
          fetchDiscoverySessions(userId, { limit: 8 }).catch(() => ({ sessions: [] })),
        ]);
        setOrchestrationState(orchestration.state ?? null);
        setDiscoverySessions(sessions.sessions ?? []);

        if (!prefsData.preferences?.conversation_complete) {
          // Need to collect preferences
          const [opener, histData] = await Promise.all([
            getPreferenceOpener(userId),
            fetchConversationHistory(userId),
          ]);
          setPrefOpener(opener);
          setPrefHistory(histData.history ?? []);
          setStep("preferences");
          return;
        }

        // 4. Check for existing companies — show them without auto-running discovery
        const companyData = await fetchDiscoveredCompanies(userId, { limit: 100 });
        setCompanies(companyData.companies);
        setStep("results");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Initialization failed");
        setStep("error");
      }
    }

    init();
  }, [userId]);

  // ── SSE Event Stream for agent progress ────────────────────────────────────
  useEffect(() => {
    if (step !== "running") {
      esRef.current?.close();
      return;
    }

    esRef.current?.close();
    const es = createEventSource((event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "connected") return;
        if (data.agent_name === "CompanyFinderAgent" || data.agent_name === "Orchestrator") {
          setAgentMessage(data.message ?? "");
          if (data.status === "completed") {
            const wasContinuing = isContinuingRef.current;
            isContinuingRef.current = false;
            // Always reload from DB so persisted state is the source of truth
            fetchDiscoveredCompanies(userId, { limit: 100 })
              .then((res) => {
                if (wasContinuing) {
                  // Merge: keep existing companies and append genuinely new ones
                  setCompanies((prev) => {
                    const existingIds = new Set(
                      prev.map((c) => c.id).filter(Boolean)
                    );
                    const existingDomains = new Set(
                      prev.map((c) => (c.domain || "").toLowerCase()).filter(Boolean)
                    );
                    const brandNew = res.companies.filter(
                      (c) =>
                        !existingIds.has(c.id) &&
                        !(c.domain && existingDomains.has(c.domain.toLowerCase()))
                    );
                    return [...prev, ...brandNew];
                  });
                } else {
                  setCompanies(res.companies);
                }
                setStep("results");
              })
              .catch(() => setStep("results"));
          } else if (data.status === "failed") {
            isContinuingRef.current = false;
            setError(data.message || "Agent failed");
            setStep("error");
          }
        }
      } catch {
        // ignore malformed events
      }
    });
    esRef.current = es;
    return () => es.close();
  }, [step, userId]);

  // ── Start discovery ────────────────────────────────────────────────────────
  const startDiscovery = useCallback(async () => {
    setStep("running");
    setAgentMessage("Starting Company Finder Agent...");
    setError(null);
    try {
      await runCompanyFinder({ user_id: userId, count: 60 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start agent");
      setStep("error");
    }
  }, [userId]);

  // ── On preference completion ───────────────────────────────────────────────
  const onPreferencesComplete = useCallback(
    async (prefs: UserPreferences) => {
      setPreferences(prefs);
      await startDiscovery();
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
        await fetchDiscoveredCompanies(userId, { limit: 50 }).then((data) => setCompanies(data.companies));
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
        await fetchDiscoveredCompanies(userId, { limit: 50 }).then((data) => setCompanies(data.companies));
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
        await fetchDiscoveredCompanies(userId, { limit: 50 }).then((data) => setCompanies(data.companies));
      }
    },
    [userId]
  );

  const onFindMoreCompanies = useCallback(async () => {
    isContinuingRef.current = true;
    setStep("running");
    setAgentMessage("Continuing discovery and expanding your persistent workspace...");
    setError(null);
    try {
      await continueCompanyDiscovery({
        user_id: userId,
        count: 40,
        source_mode: sourceMode === "all" ? undefined : sourceMode,
      });
    } catch (err) {
      isContinuingRef.current = false;
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

  if (step === "running") {
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

  // ── Results ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
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
              {companies.length} companies discovered and ranked for you
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
            onClick={startDiscovery}
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
                  startDiscovery();
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
