"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  Bot,
  Check,
  ChevronRight,
  Clock,
  Copy,
  GitCompare,
  History,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Star,
  UserRound,
  Wand2,
  X,
  Zap,
} from "lucide-react";
import { RequireAuth } from "@/components/RequireAuth";
import { useAuth } from "@/components/AuthProvider";
import {
  compareEmailVersions,
  discoverOutreachContacts,
  fetchDiscoveredCompanies,
  fetchEmailDraft,
  fetchEmailDrafts,
  fetchOutreachContacts,
  fetchPersonalization,
  generateEmailDraft,
  requestInlineAIEdit,
  restoreEmailVersion,
  updateEmailDraft,
} from "@/lib/api";
import type {
  Company,
  EmailDraft,
  EmailVersion,
  OutreachContact,
  PersonalizationProfile,
} from "@/lib/types";

// â”€â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const QUICK_ACTIONS = [
  "make this shorter",
  "sound more confident",
  "make this friendlier",
  "rewrite professionally",
  "make this startup-style",
  "remove fluff",
  "mention my AI experience",
  "improve the opening",
  "strengthen the CTA",
];

type RightTab = "personalization" | "contacts" | "history";

interface ToolbarState {
  x: number;
  y: number;
  selectedText: string;
}

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  text: string;
}

interface GenerateState {
  companyId: string;
  outreachType: string;
}

// â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function parseDiff(diff: string): DiffLine[] {
  return diff
    .split("\n")
    .filter((l) => !l.startsWith("---") && !l.startsWith("+++") && !l.startsWith("@@"))
    .map((l) => ({
      type: (l.startsWith("+") ? "added" : l.startsWith("-") ? "removed" : "unchanged") as DiffLine["type"],
      text: l.startsWith("+") || l.startsWith("-") ? l.slice(1) : l,
    }));
}

function formatDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// â”€â”€â”€ Main Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function ReviewPage() {
  const { session, loading: authLoading } = useAuth();
  const userId = session?.user?.id;

  // â”€â”€â”€ Data state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<EmailDraft | null>(null);
  const [versions, setVersions] = useState<EmailVersion[]>([]);
  const [contacts, setContacts] = useState<OutreachContact[]>([]);
  const [personalization, setPersonalization] = useState<PersonalizationProfile | null>(null);

  // â”€â”€â”€ UI state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generatingFor, setGeneratingFor] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<string | null>(null);
  const [typedDraftId, setTypedDraftId] = useState<string | null>(null);
  const [typedBody, setTypedBody] = useState("");

  // â”€â”€â”€ AI editing state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [toolbar, setToolbar] = useState<ToolbarState | null>(null);
  const [customInstruction, setCustomInstruction] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPreview, setAiPreview] = useState<{
    ai_edit_request_id: string;
    original_text: string;
    replacement_text: string;
    updated_body: string;
    diff: string;
    rationale: string;
  } | null>(null);

  // â”€â”€â”€ Version compare state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [compareLeft, setCompareLeft] = useState<EmailVersion | null>(null);
  const [compareRight, setCompareRight] = useState<EmailVersion | null>(null);
  const [compareDiff, setCompareDiff] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);

  // â”€â”€â”€ Panel state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [rightTab, setRightTab] = useState<RightTab>("personalization");

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const saveDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoGenerateKeyRef = useRef<string | null>(null);

  // â”€â”€â”€ Effects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    if (authLoading) return;
    if (!userId) {
      setLoading(false);
      setLoadError("Sign in to review your drafts.");
      return;
    }
    void loadAll(userId);
  }, [authLoading, userId]);

  useEffect(() => {
    if (authLoading || !userId || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const companyId = params.get("generate");
    if (!companyId) return;
    const outreachType = params.get("type") || "cold_email";
    const key = `${userId}:${companyId}:${outreachType}`;
    if (autoGenerateKeyRef.current === key) return;
    autoGenerateKeyRef.current = key;
    void generateForCompanyId(companyId, outreachType);
  }, [authLoading, userId]);

  useEffect(() => {
    if (!selectedId || !userId) return;
    void loadSelected(selectedId, userId);
  }, [selectedId, userId]);

  useEffect(() => {
    if (!typedDraftId || !selectedDraft || selectedDraft.id !== typedDraftId) return;
    const fullBody = selectedDraft.body || "";
    setTypedBody("");
    let index = 0;
    const timer = setInterval(() => {
      index = Math.min(index + 10, fullBody.length);
      setTypedBody(fullBody.slice(0, index));
      if (index >= fullBody.length) {
        clearInterval(timer);
        setTypedDraftId(null);
      }
    }, 16);

    return () => clearInterval(timer);
  }, [selectedDraft, typedDraftId]);

  // Dismiss floating toolbar when clicking outside
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (
        toolbarRef.current &&
        !toolbarRef.current.contains(e.target as Node) &&
        textareaRef.current &&
        !textareaRef.current.contains(e.target as Node)
      ) {
        setToolbar(null);
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, []);

  // â”€â”€â”€ Data loading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function loadAll(uid: string) {
    setLoading(true);
    setLoadError(null);
    try {
      const [draftsRes, companiesRes] = await Promise.allSettled([
        fetchEmailDrafts(uid),
        fetchDiscoveredCompanies(uid, { limit: 100 }),
      ]);
      const loadedDrafts = draftsRes.status === "fulfilled" ? draftsRes.value.drafts : [];
      const loadedCompanies =
        companiesRes.status === "fulfilled"
          ? (companiesRes.value.visible_companies ?? companiesRes.value.companies ?? [])
          : [];
      setDrafts(loadedDrafts);
      setCompanies(loadedCompanies);
      if (loadedDrafts.length > 0) {
        setSelectedId((cur) => {
          if (cur && loadedDrafts.some((d) => d.id === cur)) return cur;
          return loadedDrafts[0].id;
        });
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSelected(draftId: string, uid: string) {
    try {
      const result = await fetchEmailDraft(draftId);
      setSelectedDraft(result.draft);
      setVersions(result.versions);
      setAiPreview(null);
      setToolbar(null);
      setCompareLeft(null);
      setCompareRight(null);
      setCompareDiff(null);
      const [profileRes, contactsRes] = await Promise.allSettled([
        fetchPersonalization(result.draft.company_id, uid),
        fetchOutreachContacts(result.draft.company_id, uid),
      ]);
      setPersonalization(profileRes.status === "fulfilled" ? profileRes.value.profile : null);
      setContacts(contactsRes.status === "fulfilled" ? contactsRes.value.contacts : []);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load draft.");
    }
  }

  // â”€â”€â”€ Save helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const persistSave = useCallback(
    async (updates: Partial<EmailDraft>) => {
      if (!selectedDraft || !userId) return;
      setSaving(true);
      const optimistic = { ...selectedDraft, ...updates };
      setSelectedDraft(optimistic);
      setDrafts((prev) => prev.map((d) => (d.id === optimistic.id ? optimistic : d)));
      try {
        const res = await updateEmailDraft(selectedDraft.id, { user_id: userId, ...updates });
        setSelectedDraft(res.draft);
        setDrafts((prev) => prev.map((d) => (d.id === res.draft.id ? res.draft : d)));
        if ("body" in updates || "subject" in updates) {
          const refreshed = await fetchEmailDraft(selectedDraft.id);
          setVersions(refreshed.versions);
        }
      } catch {
        setSelectedDraft(selectedDraft); // revert
      } finally {
        setSaving(false);
      }
    },
    [selectedDraft, userId]
  );

  const debouncedSave = useCallback(
    (updates: Partial<EmailDraft>) => {
      if (saveDebounce.current) clearTimeout(saveDebounce.current);
      saveDebounce.current = setTimeout(() => void persistSave(updates), 1500);
    },
    [persistSave]
  );

  function handleBodyChange(value: string) {
    if (!selectedDraft) return;
    setTypedDraftId(null);
    setTypedBody("");
    setSelectedDraft({ ...selectedDraft, body: value });
    debouncedSave({ body: value });
  }

  function handleSubjectChange(value: string) {
    if (!selectedDraft) return;
    setSelectedDraft({ ...selectedDraft, subject: value });
    debouncedSave({ subject: value });
  }

  // â”€â”€â”€ Selection / floating toolbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function onTextareaMouseUp(e: React.MouseEvent<HTMLTextAreaElement>) {
    const node = e.currentTarget;
    const start = node.selectionStart;
    const end = node.selectionEnd;
    if (end > start) {
      const text = node.value.slice(start, end);
      setToolbar({ x: e.clientX, y: e.clientY, selectedText: text });
      setCustomInstruction("");
      setAiPreview(null);
    } else {
      setToolbar(null);
    }
  }

  // â”€â”€â”€ AI editing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function runAIEdit(instruction: string) {
    if (!selectedDraft || !userId) return;
    const selected = toolbar?.selectedText ?? selectedDraft.body;
    setAiLoading(true);
    setToolbar(null);
    try {
      const preview = await requestInlineAIEdit(selectedDraft.id, {
        user_id: userId,
        instruction,
        selected_text: selected,
        full_body: selectedDraft.body,
        subject: selectedDraft.subject,
      });
      setAiPreview(preview);
    } finally {
      setAiLoading(false);
    }
  }

  async function acceptAIEdit() {
    if (!aiPreview) return;
    await persistSave({ body: aiPreview.updated_body });
    setAiPreview(null);
  }

  // â”€â”€â”€ Version restore / compare â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function restoreVersion(version: EmailVersion) {
    if (!selectedDraft || !userId) return;
    const res = await restoreEmailVersion(selectedDraft.id, version.id, userId);
    setSelectedDraft(res.draft);
    if (userId) await loadSelected(selectedDraft.id, userId);
  }

  async function runVersionCompare(left: EmailVersion, right: EmailVersion) {
    if (!selectedDraft) return;
    setCompareLeft(left);
    setCompareRight(right);
    setComparing(true);
    try {
      const res = await compareEmailVersions(selectedDraft.id, left.id, right.id);
      setCompareDiff(res.body_diff ?? null);
    } catch {
      setCompareDiff(null);
    } finally {
      setComparing(false);
    }
  }

  // â”€â”€â”€ Generate draft for company â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function generateForCompanyId(companyId: string, outreachType = "cold_email") {
    if (!userId) return;
    setGeneratingFor(companyId);
    setGenerationStatus("Collecting your resume, preferences, and company context...");
    setLoadError(null);
    try {
      setGenerationStatus("Writing a polished first-person cold email...");
      const res = await generateEmailDraft({ user_id: userId, company_id: companyId, outreach_type: outreachType });
      const newDraft = res.draft;
      setDrafts((prev) => {
        const exists = prev.find((d) => d.company_id === companyId);
        return exists ? prev.map((d) => (d.company_id === companyId ? newDraft : d)) : [newDraft, ...prev];
      });
      setSelectedDraft(newDraft);
      setSelectedId(newDraft.id);
      setPersonalization(res.personalization);
      setTypedDraftId(newDraft.id);
      setTypedBody("");
      setGenerationStatus("Draft ready. Typing it into the editor...");
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        url.searchParams.delete("generate");
        url.searchParams.delete("type");
        url.searchParams.set("draft", newDraft.id);
        window.history.replaceState(null, "", `${url.pathname}${url.search}`);
      }
    } catch (err) {
      console.error("Failed to generate draft", err);
      setLoadError(err instanceof Error ? err.message : "Failed to generate draft.");
    } finally {
      setGeneratingFor(null);
      setTimeout(() => setGenerationStatus(null), 1200);
    }
  }

  async function generateForCompany(company: Company, outreachType = "cold_email") {
    await generateForCompanyId(company.id, outreachType);
  }

  // â”€â”€â”€ Refresh contacts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function refreshContacts() {
    if (!selectedDraft || !userId) return;
    const res = await discoverOutreachContacts({ user_id: userId, company_id: selectedDraft.company_id });
    setContacts(res.contacts);
  }

  // â”€â”€â”€ Derived state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const draftedCompanyIds = useMemo(() => new Set(drafts.map((d) => d.company_id)), [drafts]);
  const companiesWithoutDraft = useMemo(
    () => companies.filter((c) => !draftedCompanyIds.has(c.id)).slice(0, 30),
    [companies, draftedCompanyIds]
  );
  const selectedSubjects = useMemo(
    () =>
      selectedDraft?.subjects?.length
        ? selectedDraft.subjects
        : selectedDraft
        ? [{ label: "Current", subject: selectedDraft.subject }]
        : [],
    [selectedDraft]
  );
  const selectedVariants = useMemo(
    () => (selectedDraft?.variants ? Object.keys(selectedDraft.variants) : []),
    [selectedDraft]
  );

  // â”€â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  return (
    <RequireAuth>
      {/* Floating toolbar (portal-like fixed position) */}
      {toolbar && !aiLoading && !aiPreview && (
        <FloatingAIToolbar
          ref={toolbarRef}
          position={toolbar}
          onAction={(a) => void runAIEdit(a)}
          onDismiss={() => setToolbar(null)}
        />
      )}

      <div className="flex min-h-[calc(100vh-4rem)] flex-col bg-background">
        {/* Header */}
        <header className="shrink-0 border-b border-border bg-card/70">
          <div className="mx-auto flex max-w-400 items-center justify-between px-4 py-3 sm:px-6">
            <div>
              <h1 className="text-xl font-semibold text-foreground">Email Review</h1>
              <p className="mt-0.5 text-xs text-muted-foreground">
                AI-personalized drafts Â· inline editing Â· version history
              </p>
            </div>
            <div className="flex items-center gap-3">
              {saving && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Savingâ€¦
                </span>
              )}
              {!saving && selectedDraft && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-600">
                  <Check className="h-3.5 w-3.5" /> Saved
                </span>
              )}
              {userId && (
                <button
                  onClick={() => void loadAll(userId)}
                  className="rounded-md border border-border p-2 text-muted-foreground hover:text-foreground"
                  title="Refresh"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </header>

        {generationStatus && (
          <div className="border-b border-primary/20 bg-primary/8">
            <div className="mx-auto flex max-w-400 items-center gap-2 px-4 py-2 text-sm text-primary sm:px-6">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{generationStatus}</span>
            </div>
          </div>
        )}

        {/* Three-panel grid */}
        <div className="flex-1 overflow-hidden lg:grid lg:grid-cols-[260px_minmax(0,1fr)_320px]">

          {/* â”€â”€ Sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          <aside className="overflow-y-auto border-b border-border bg-card/40 lg:border-b-0 lg:border-r lg:max-h-[calc(100vh-7rem)]">
            <div className="sticky top-0 z-10 border-b border-border/40 bg-card/80 px-4 py-2.5 backdrop-blur-sm">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {drafts.length} Draft{drafts.length !== 1 ? "s" : ""}
                {companiesWithoutDraft.length > 0 && ` Â· ${companiesWithoutDraft.length} pending`}
              </span>
            </div>

            {loading ? (
              <div className="flex items-center gap-2 px-4 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loadingâ€¦
              </div>
            ) : (
              <>
                {/* Existing drafts */}
                {drafts.map((draft) => (
                  <button
                    key={draft.id}
                    onClick={() => setSelectedId(draft.id)}
                    className={`w-full border-l-2 px-4 py-3 text-left transition-colors ${
                      draft.id === selectedId
                        ? "border-primary bg-primary/8 text-foreground"
                        : "border-transparent text-foreground/80 hover:bg-muted/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{draft.company_name}</span>
                      <StatusPill status={draft.status} />
                    </div>
                    <div className="mt-0.5 truncate text-xs text-muted-foreground">{draft.subject}</div>
                  </button>
                ))}

                {/* Companies needing drafts */}
                {companiesWithoutDraft.length > 0 && (
                  <>
                    <div className="mt-1 border-t border-border/40 px-4 py-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/60">
                        Generate Draft
                      </span>
                    </div>
                    {companiesWithoutDraft.map((company) => (
                      <div
                        key={company.id}
                        className="flex items-center justify-between border-l-2 border-transparent px-4 py-2.5 hover:bg-muted/20"
                      >
                        <span className="truncate text-sm text-muted-foreground">{company.name}</span>
                        <button
                          onClick={() => void generateForCompany(company)}
                          disabled={generatingFor === company.id}
                          className="ml-2 flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-primary disabled:opacity-40"
                        >
                          {generatingFor === company.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Plus className="h-3 w-3" />
                          )}
                          {generatingFor === company.id ? "" : "Draft"}
                        </button>
                      </div>
                    ))}
                  </>
                )}

                {!loading && drafts.length === 0 && companiesWithoutDraft.length === 0 && (
                  <div className="space-y-2 px-4 py-8 text-sm text-muted-foreground">
                    <p>{loadError ?? "No drafts yet. Run the Company Finder first."}</p>
                    {userId && (
                      <button
                        onClick={() => void loadAll(userId)}
                        className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
                      >
                        Retry
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
          </aside>

          {/* â”€â”€ Canvas Editor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          <main className="overflow-y-auto lg:max-h-[calc(100vh-7rem)]">
            {!selectedDraft ? (
              <EmptyEditor loading={loading} error={loadError} onRetry={() => userId && void loadAll(userId)} />
            ) : (
              <div className="mx-auto max-w-3xl space-y-5 px-4 py-6 sm:px-6">

                {/* Actions bar */}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-64 space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">To</label>
                    <select
                      value={selectedDraft.recipient_email ?? ""}
                      onChange={(e) => void persistSave({ recipient_email: e.target.value })}
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                    >
                      <option value="">Choose recipientâ€¦</option>
                      {contacts.map((c) => (
                        <option key={c.email} value={c.email}>
                          {c.name ? `${c.name} (${c.role ?? ""})` : c.role} â€” {c.email}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => void persistSave({ status: "approved" })}
                      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition ${
                        selectedDraft.status === "approved"
                          ? "bg-emerald-600 text-white"
                          : "border border-emerald-600/40 text-emerald-600 hover:bg-emerald-600 hover:text-white"
                      }`}
                    >
                      <Check className="h-4 w-4" />
                      {selectedDraft.status === "approved" ? "Approved" : "Approve"}
                    </button>
                    <button
                      onClick={() => void persistSave({ status: "sent" })}
                      className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
                    >
                      <Send className="h-4 w-4" />
                      Mark Sent
                    </button>
                    <button
                      onClick={() => void persistSave({ status: "rejected" })}
                      title="Reject"
                      className="rounded-md border border-border p-2 text-muted-foreground hover:text-red-500"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Variant tabs */}
                {selectedVariants.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground">Variant:</span>
                    {selectedVariants.map((key) => (
                      <button
                        key={key}
                        onClick={() =>
                          void persistSave({ selected_variant: key, body: selectedDraft.variants[key] ?? "" })
                        }
                        className={`rounded-md border px-3 py-1 text-xs font-medium transition ${
                          selectedDraft.selected_variant === key
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground"
                        }`}
                      >
                        {key.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                )}

                {/* Subject */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="w-14 shrink-0 text-xs text-muted-foreground">Subject</span>
                    {selectedSubjects.length > 1 && (
                      <select
                        value={selectedDraft.subject}
                        onChange={(e) => void persistSave({ subject: e.target.value })}
                        className="max-w-52 rounded border border-border bg-background px-2 py-1 text-xs text-muted-foreground"
                      >
                        {selectedSubjects.map((s) => (
                          <option key={`${s.label}|${s.subject}`} value={s.subject}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  <input
                    value={selectedDraft.subject}
                    onChange={(e) => handleSubjectChange(e.target.value)}
                    placeholder="Email subjectâ€¦"
                    className="w-full rounded-md border border-border bg-background px-4 py-3 text-base font-medium text-foreground outline-none placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-primary/30"
                  />
                </div>

                {/* Body editor */}
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={typedDraftId === selectedDraft.id ? typedBody : selectedDraft.body}
                    onChange={(e) => handleBodyChange(e.target.value)}
                    onMouseUp={onTextareaMouseUp}
                    rows={22}
                    placeholder="Email bodyâ€¦"
                    className="min-h-125 w-full resize-y rounded-md border border-border bg-background px-5 py-4 font-mono text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/30 focus:ring-2 focus:ring-primary/30"
                  />
                  {aiLoading && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-md bg-background/70">
                      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 shadow-sm">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        <span className="text-sm">Generating AI editâ€¦</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* AI diff preview */}
                {aiPreview && (
                  <AIDiffPreview
                    preview={aiPreview}
                    onAccept={() => void acceptAIEdit()}
                    onReject={() => setAiPreview(null)}
                  />
                )}

                {/* AI toolbar (non-floating / always visible strip) */}
                <div className="rounded-md border border-border bg-card/60 p-3 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Wand2 className="h-4 w-4 shrink-0 text-primary" />
                    <input
                      value={customInstruction}
                      onChange={(e) => setCustomInstruction(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && customInstruction.trim()) void runAIEdit(customInstruction.trim());
                      }}
                      placeholder="Custom instruction (e.g. 'make the opening bold')â€¦ or select text above"
                      className="min-w-48 flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                    <button
                      onClick={() => customInstruction.trim() && void runAIEdit(customInstruction.trim())}
                      disabled={aiLoading || !customInstruction.trim()}
                      className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
                    >
                      {aiLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      Apply
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {QUICK_ACTIONS.slice(0, 7).map((a) => (
                      <button
                        key={a}
                        onClick={() => void runAIEdit(a)}
                        disabled={aiLoading}
                        className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground disabled:opacity-40"
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Metadata footer */}
                <div className="flex flex-wrap items-center gap-4 border-t border-border/40 pt-3 text-xs text-muted-foreground">
                  <span>v{selectedDraft.version_number}</span>
                  <span className="capitalize">{selectedDraft.outreach_type?.replace(/_/g, " ")}</span>
                  {selectedDraft.last_edited_at && <span>Edited {formatDate(selectedDraft.last_edited_at)}</span>}
                </div>
              </div>
            )}
          </main>

          {/* â”€â”€ Right Panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          <aside className="border-l border-border bg-card/30 overflow-y-auto lg:max-h-[calc(100vh-7rem)]">
            {/* Tabs */}
            <div className="sticky top-0 z-10 flex border-b border-border/40 bg-card/80 backdrop-blur-sm">
              {(["personalization", "contacts", "history"] as RightTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setRightTab(tab)}
                  className={`flex flex-1 items-center justify-center gap-1 py-2.5 text-xs font-medium capitalize transition ${
                    rightTab === tab
                      ? "border-b-2 border-primary text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab === "personalization" && <Bot className="h-3.5 w-3.5" />}
                  {tab === "contacts" && <UserRound className="h-3.5 w-3.5" />}
                  {tab === "history" && <History className="h-3.5 w-3.5" />}
                  {tab === "personalization" ? "Fit" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            <div className="p-4">
              {rightTab === "personalization" && <PersonalizationPanel profile={personalization} />}
              {rightTab === "contacts" && (
                <ContactsPanel
                  contacts={contacts}
                  selectedEmail={selectedDraft?.recipient_email ?? null}
                  onSelect={(email) => selectedDraft && void persistSave({ recipient_email: email })}
                  onRefresh={() => void refreshContacts()}
                />
              )}
              {rightTab === "history" && (
                <VersionPanel
                  versions={versions}
                  compareLeft={compareLeft}
                  compareRight={compareRight}
                  compareDiff={compareDiff}
                  comparing={comparing}
                  onRestore={(v) => void restoreVersion(v)}
                  onCompare={(l, r) => void runVersionCompare(l, r)}
                  onClearCompare={() => {
                    setCompareLeft(null);
                    setCompareRight(null);
                    setCompareDiff(null);
                  }}
                />
              )}
            </div>
          </aside>
        </div>
      </div>
    </RequireAuth>
  );
}

// â”€â”€â”€ FloatingAIToolbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const FloatingAIToolbar = ({
  ref,
  position,
  onAction,
  onDismiss,
}: {
  ref: React.RefObject<HTMLDivElement | null>;
  position: ToolbarState;
  onAction: (action: string) => void;
  onDismiss: () => void;
}) => {
  // Keep inside viewport
  const safeX = typeof window !== "undefined" ? Math.min(Math.max(8, position.x - 140), window.innerWidth - 300) : position.x;
  const safeY = typeof window !== "undefined" ? Math.max(8, position.y - 80) : position.y;

  return (
    <div
      ref={ref}
      style={{ position: "fixed", left: safeX, top: safeY, zIndex: 9999 }}
      className="w-72 rounded-lg border border-border bg-card shadow-xl"
    >
      <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          AI Edit Â· <span className="text-foreground">{position.selectedText.length} chars selected</span>
        </div>
        <button onClick={onDismiss} className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 p-2.5">
        {QUICK_ACTIONS.map((a) => (
          <button
            key={a}
            onClick={() => onAction(a)}
            className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-foreground hover:bg-primary hover:text-primary-foreground transition"
          >
            {a}
          </button>
        ))}
      </div>
    </div>
  );
};

// â”€â”€â”€ AIDiffPreview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AIDiffPreview({
  preview,
  onAccept,
  onReject,
}: {
  preview: {
    original_text: string;
    replacement_text: string;
    updated_body: string;
    diff: string;
    rationale: string;
  };
  onAccept: () => void;
  onReject: () => void;
}) {
  const diffLines = useMemo(() => parseDiff(preview.diff), [preview.diff]);
  return (
    <div className="rounded-lg border border-primary/20 bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-primary" />
          AI Edit Preview
        </div>
        <button onClick={onReject} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">Proposed</div>
          <div className="max-h-48 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-sm whitespace-pre-wrap">
            {preview.replacement_text}
          </div>
        </div>
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground">Diff</div>
          <div className="max-h-48 overflow-auto rounded-md border border-border bg-muted/20 p-2">
            {diffLines.length > 0 ? (
              diffLines.map((line, i) => (
                <div
                  key={i}
                  className={`px-2 py-0.5 font-mono text-xs ${
                    line.type === "added"
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                      : line.type === "removed"
                      ? "bg-red-500/10 text-red-600 dark:text-red-400 line-through"
                      : "text-muted-foreground"
                  }`}
                >
                  {line.text || " "}
                </div>
              ))
            ) : (
              <p className="p-2 text-xs text-muted-foreground">Full replacement (no line diff).</p>
            )}
          </div>
        </div>
      </div>

      {preview.rationale && <p className="text-xs italic text-muted-foreground">{preview.rationale}</p>}

      <div className="flex gap-2">
        <button
          onClick={onAccept}
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white"
        >
          <Check className="h-4 w-4" /> Accept
        </button>
        <button
          onClick={onReject}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-muted-foreground"
        >
          <X className="h-4 w-4" /> Reject
        </button>
      </div>
    </div>
  );
}

// â”€â”€â”€ PersonalizationPanel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function PersonalizationPanel({ profile }: { profile: PersonalizationProfile | null }) {
  if (!profile) {
    return (
      <div className="rounded-md border border-border/40 bg-muted/20 p-4 text-sm text-muted-foreground">
        No personalization profile for this draft.
      </div>
    );
  }
  return (
    <div className="space-y-4 text-sm">
      {/* Fit score */}
      <div className="flex items-center justify-between rounded-md border border-border bg-background p-3">
        <span className="font-medium text-foreground">Fit Score</span>
        <div className="flex items-center gap-2">
          <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${profile.fit_score}%` }}
            />
          </div>
          <span className="font-semibold text-primary">{profile.fit_score}</span>
        </div>
      </div>

      {/* Summary */}
      <p className="text-xs leading-relaxed text-muted-foreground">{profile.personalization_summary}</p>

      {/* Alignment */}
      {profile.company_alignment.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground/60">Alignment</div>
          <ul className="space-y-1">
            {profile.company_alignment.map((a) => (
              <li key={a} className="flex items-start gap-1.5 text-xs text-foreground">
                <Zap className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Skills */}
      {profile.relevant_skills.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground/60">Relevant Skills</div>
          <div className="flex flex-wrap gap-1.5">
            {profile.relevant_skills.slice(0, 10).map((s) => (
              <span key={s} className="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Hooks */}
      {profile.recommended_hooks.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground/60">Hooks</div>
          <ul className="space-y-1.5">
            {profile.recommended_hooks.slice(0, 3).map((h) => (
              <li key={h} className="rounded-md bg-muted/40 p-2 text-xs text-foreground">{h}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggested links */}
      {profile.suggested_links.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase text-muted-foreground/60">Include Links</div>
          <ul className="space-y-1">
            {profile.suggested_links.map((l) => (
              <li key={l.url ?? l.type} className="flex items-center gap-1.5 text-xs">
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
                <span className="font-medium capitalize text-foreground">{l.type}</span>
                <span className="truncate text-muted-foreground">{l.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// â”€â”€â”€ ContactsPanel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function ContactsPanel({
  contacts,
  selectedEmail,
  onSelect,
  onRefresh,
}: {
  contacts: OutreachContact[];
  selectedEmail: string | null;
  onSelect: (email: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-muted-foreground/60">Ranked Contacts</span>
        <button onClick={onRefresh} className="text-muted-foreground hover:text-foreground" title="Rediscover">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {contacts.length === 0 ? (
        <div className="rounded-md border border-border/40 bg-muted/20 p-4 text-xs text-muted-foreground">
          No contacts found. Click refresh to discover.
        </div>
      ) : (
        contacts.map((c) => {
          const isSelected = c.email === selectedEmail;
          return (
            <button
              key={c.email}
              onClick={() => onSelect(c.email)}
              className={`w-full rounded-md border p-3 text-left transition ${
                isSelected
                  ? "border-primary bg-primary/8"
                  : "border-border bg-background hover:border-primary/40"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-foreground">
                    {c.name || c.email}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">
                    {c.role || c.contact_type} Â· {c.email}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="text-xs font-semibold text-primary">{c.priority_score}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {Math.round(c.confidence * 100)}%
                  </span>
                </div>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <ContactTypeBadge type={c.contact_type} />
                {c.verified && (
                  <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
                    Verified
                  </span>
                )}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}

// â”€â”€â”€ VersionPanel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function VersionPanel({
  versions,
  compareLeft,
  compareRight,
  compareDiff,
  comparing,
  onRestore,
  onCompare,
  onClearCompare,
}: {
  versions: EmailVersion[];
  compareLeft: EmailVersion | null;
  compareRight: EmailVersion | null;
  compareDiff: string | null;
  comparing: boolean;
  onRestore: (v: EmailVersion) => void;
  onCompare: (l: EmailVersion, r: EmailVersion) => void;
  onClearCompare: () => void;
}) {
  const [selectingCompare, setSelectingCompare] = useState(false);
  const [firstPick, setFirstPick] = useState<EmailVersion | null>(null);

  function pickVersion(v: EmailVersion) {
    if (!selectingCompare) return;
    if (!firstPick) {
      setFirstPick(v);
    } else if (firstPick.id !== v.id) {
      onCompare(firstPick, v);
      setSelectingCompare(false);
      setFirstPick(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-muted-foreground/60">Version History</span>
        {versions.length >= 2 && (
          <button
            onClick={() => {
              setSelectingCompare((v) => !v);
              setFirstPick(null);
              onClearCompare();
            }}
            className={`flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition ${
              selectingCompare
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            <GitCompare className="h-3 w-3" />
            Compare
          </button>
        )}
      </div>

      {selectingCompare && (
        <div className="rounded-md border border-primary/20 bg-primary/5 p-2 text-xs text-primary">
          {!firstPick ? "Select first versionâ€¦" : `First: v${firstPick.version_number} â€” now select secondâ€¦`}
        </div>
      )}

      {/* Diff result */}
      {(comparing || compareDiff !== null) && (
        <div className="rounded-md border border-border bg-background p-3 space-y-2">
          <div className="flex items-center justify-between text-xs font-medium">
            <span>
              v{compareLeft?.version_number} â†’ v{compareRight?.version_number}
            </span>
            <button onClick={onClearCompare} className="text-muted-foreground hover:text-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {comparing ? (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Computing diffâ€¦
            </div>
          ) : compareDiff ? (
            <div className="max-h-52 overflow-auto">
              {parseDiff(compareDiff).map((line, i) => (
                <div
                  key={i}
                  className={`px-2 py-0.5 font-mono text-[11px] ${
                    line.type === "added"
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                      : line.type === "removed"
                      ? "bg-red-500/10 text-red-600 dark:text-red-400 line-through"
                      : "text-muted-foreground"
                  }`}
                >
                  {line.text || " "}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No differences.</p>
          )}
        </div>
      )}

      {/* Version list */}
      {versions.length === 0 ? (
        <div className="rounded-md border border-border/40 bg-muted/20 p-4 text-xs text-muted-foreground">
          No versions saved yet.
        </div>
      ) : (
        <div className="space-y-1.5">
          {versions.map((v) => {
            const isFirstPick = firstPick?.id === v.id;
            return (
              <div
                key={v.id}
                onClick={() => pickVersion(v)}
                className={`rounded-md border p-3 transition ${
                  isFirstPick
                    ? "border-primary bg-primary/8"
                    : selectingCompare
                    ? "cursor-pointer border-border hover:border-primary/40"
                    : "border-border bg-background"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-foreground">Version {v.version_number}</div>
                  {!selectingCompare && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRestore(v);
                      }}
                      className="text-muted-foreground hover:text-primary"
                      title="Restore"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="capitalize">{v.event_type?.replace(/_/g, " ")}</span>
                  <span>by {v.editor}</span>
                  {v.created_at && <span>{formatDate(v.created_at)}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// â”€â”€â”€ EmptyEditor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function EmptyEditor({
  loading,
  error,
  onRetry,
}: {
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center text-muted-foreground">
      {loading ? (
        <>
          <Loader2 className="h-8 w-8 animate-spin" />
          <span>Loading draftsâ€¦</span>
        </>
      ) : (
        <>
          <Mail className="h-12 w-12 text-muted-foreground/20" />
          <div className="space-y-1">
            <p className="font-medium text-foreground">No draft selected</p>
            <p className="text-sm">{error ?? "Select a company from the sidebar or generate a new draft."}</p>
          </div>
          {error && (
            <button
              onClick={onRetry}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              Retry
            </button>
          )}
        </>
      )}
    </div>
  );
}

// â”€â”€â”€ StatusPill â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function StatusPill({ status }: { status: EmailDraft["status"] }) {
  const cls =
    status === "approved"
      ? "bg-emerald-500/10 text-emerald-600"
      : status === "sent"
      ? "bg-primary/10 text-primary"
      : status === "rejected"
      ? "bg-red-500/10 text-red-600"
      : "bg-amber-500/10 text-amber-600";
  return (
    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium capitalize ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

// â”€â”€â”€ ContactTypeBadge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function ContactTypeBadge({ type }: { type: OutreachContact["contact_type"] }) {
  const labels: Record<OutreachContact["contact_type"], { label: string; cls: string }> = {
    founder: { label: "Founder", cls: "bg-violet-500/10 text-violet-600" },
    recruiter: { label: "Recruiter", cls: "bg-blue-500/10 text-blue-600" },
    hiring_manager: { label: "Hiring Mgr", cls: "bg-sky-500/10 text-sky-600" },
    engineer: { label: "Engineer", cls: "bg-orange-500/10 text-orange-600" },
    hr: { label: "HR", cls: "bg-pink-500/10 text-pink-600" },
    other: { label: "Other", cls: "bg-muted text-muted-foreground" },
  };
  const { label, cls } = labels[type] ?? labels.other;
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>{label}</span>;
}

