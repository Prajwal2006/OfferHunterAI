"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, Play, RefreshCw, Filter, Bot, Zap, Building2, ArrowRight, Info } from "lucide-react";
import { AgentEvent, AgentInfo } from "@/lib/types";
import { MOCK_AGENTS } from "@/lib/mockData";
import AgentCard from "@/components/AgentCard";
import EventStream from "@/components/EventStream";
import OrchestrationFlow from "@/components/OrchestrationFlow";
import TaskTimeline from "@/components/TaskTimeline";
import { MOCK_PIPELINE } from "@/lib/mockData";
import { RequireAuth } from "@/components/RequireAuth";
import { fetchResumes, createEventSource, fetchOrchestrationState } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { ResumeVersion } from "@/lib/types";
import Link from "next/link";
import { useRouter } from "next/navigation";

// Map agent name tokens â†’ orchestration step IDs
const AGENT_TO_STEP: Record<string, string> = {
  CompanyFinderAgent: "CompanyFinder",
  PersonalizationAgent: "Personalization",
  EmailWriterAgent: "EmailWriter",
  ReviewAgent: "Review",
  EmailSenderAgent: "Sender",
};

function useAgentState() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>(MOCK_AGENTS);
  const [isRunning, setIsRunning] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // â”€â”€ Apply a real SSE event to agent state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const applyEvent = useCallback((ev: AgentEvent) => {
    setEvents((prev) => {
      // deduplicate by id
      if (prev.some((e) => e.id === ev.id)) return prev;
      return [ev, ...prev];
    });

    setAgents((prev) =>
      prev.map((a) => {
        if (a.name !== ev.agent_name) return a;
        const next = { ...a };
        if (ev.status === "running" || ev.status === "started") {
          next.status = "running";
          next.currentTask = ev.message;
        } else if (ev.status === "completed") {
          next.status = "completed";
          next.currentTask = ev.message;
        } else if (ev.status === "failed" || ev.status === "error") {
          next.status = "error";
          next.currentTask = ev.message;
        }
        return next;
      })
    );
  }, []);

  // â”€â”€ Demo simulation (used when user clicks "Demo") â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const simulatedMessages = [
    { agent: "CompanyFinderAgent", msg: "Scanning HackerNews 'Who's Hiring' posts...", status: "running" as const },
    { agent: "CompanyFinderAgent", msg: "Querying RemoteOK API for matching roles...", status: "running" as const },
    { agent: "CompanyFinderAgent", msg: "Asking AI to suggest companies based on your profile...", status: "running" as const },
    { agent: "CompanyFinderAgent", msg: "Ranking 28 discovered companies by match score...", status: "running" as const },
    { agent: "CompanyFinderAgent", msg: "Finding contact emails for top 10 companies...", status: "running" as const },
    { agent: "CompanyFinderAgent", msg: "Found 18 companies Â· Top match: Anthropic (94%)", status: "completed" as const },
    { agent: "PersonalizationAgent", msg: "Fetching Anthropic careers page & engineering blog...", status: "running" as const },
    { agent: "PersonalizationAgent", msg: "Extracted key themes: safety-focused, research-heavy, Python/PyTorch", status: "completed" as const },
    { agent: "EmailWriterAgent", msg: "Generating cold email for Anthropic â€” highlighting ML background...", status: "running" as const },
    { agent: "EmailWriterAgent", msg: "Email drafted for Anthropic. Awaiting your approval in Review.", status: "completed" as const },
    { agent: "ResumeTailorAgent", msg: "Tailoring resume bullets for Anthropic job descriptions...", status: "running" as const },
    { agent: "ResumeTailorAgent", msg: "Resume tailored. Added 3 bullets matching safety/alignment focus.", status: "completed" as const },
  ];

  function startDemo() {
    if (isRunning) return;
    setIsRunning(true);
    setDemoMode(true);
    // Reset agents to idle first
    setAgents(MOCK_AGENTS.map((a) => ({ ...a, status: "idle" as const, currentTask: undefined })));
    setEvents([]);

    let i = 0;
    intervalRef.current = setInterval(() => {
      if (i >= simulatedMessages.length) {
        clearInterval(intervalRef.current!);
        setIsRunning(false);
        return;
      }

      const sim = simulatedMessages[i];
      const newEvent: AgentEvent = {
        id: `demo-${Date.now()}-${i}`,
        agent_name: sim.agent,
        task_id: `task-demo-${i}`,
        status: sim.status,
        message: sim.msg,
        metadata: {},
        created_at: new Date().toISOString(),
      };

      applyEvent(newEvent);
      i++;
    }, 1800);
  }

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { events, agents, isRunning, demoMode, startDemo, applyEvent };
}

export default function AgentsPage() {
  const { events, agents, isRunning, demoMode, startDemo, applyEvent } = useAgentState();
  const { session } = useAuth();
  const router = useRouter();
  const [filterAgent, setFilterAgent] = useState<string>("all");
  const [activeResume, setActiveResume] = useState<ResumeVersion | null>(null);
  const [persistedStage, setPersistedStage] = useState<string | undefined>(undefined);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  // Derive active step from agent states
  const runningAgent = agents.find((a) => a.status === "running");
  const activeStep = runningAgent ? AGENT_TO_STEP[runningAgent.name] : persistedStage;

  const filteredEvents =
    filterAgent === "all"
      ? events
      : events.filter((e) => e.agent_name === filterAgent);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = 0;
    }
  }, [events]);

  // â”€â”€ Connect to real SSE stream â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  useEffect(() => {
    esRef.current?.close();

    const es = createEventSource((ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "connected") return;
        const event: AgentEvent = {
          id: data.id ?? `sse-${Date.now()}`,
          agent_name: data.agent_name ?? "Unknown",
          task_id: data.task_id ?? "",
          status: data.status ?? "running",
          message: data.message ?? "",
          metadata: data.metadata ?? {},
          created_at: data.created_at ?? new Date().toISOString(),
        };
        applyEvent(event);
      } catch {
        // ignore malformed
      }
    });
    esRef.current = es;

    return () => es.close();
  }, [applyEvent]);

  useEffect(() => {
    async function loadActiveResume() {
      const userId = session?.user?.id;
      if (!userId) return;
      try {
        const result = await fetchResumes(userId);
        const resumes = (result.resumes || []) as ResumeVersion[];
        const active = resumes.find((r) => r.is_active) || null;
        setActiveResume(active);
      } catch {
        setActiveResume(null);
      }
    }
    loadActiveResume();
  }, [session?.user?.id]);

  useEffect(() => {
    async function loadOrchestrationState() {
      const userId = session?.user?.id;
      if (!userId) return;
      try {
        const response = await fetchOrchestrationState(userId);
        const stage = response.state?.current_stage;
        if (typeof stage === "string" && stage.length > 0) {
          setPersistedStage(stage);
        }
      } catch {
        setPersistedStage(undefined);
      }
    }
    loadOrchestrationState();
  }, [session?.user?.id]);

  const handleResumeFromStep = useCallback(
    (stepId: string) => {
      if (stepId === "CompanyFinder") {
        router.push("/company-finder");
        return;
      }
      if (stepId === "Personalization" || stepId === "EmailWriter") {
        router.push("/pipeline");
        return;
      }
      if (stepId === "Review") {
        router.push("/review");
        return;
      }
      if (stepId === "Sender") {
        router.push("/analytics");
      }
    },
    [router]
  );

  const handleAgentCardClick = useCallback(
    (agent: AgentInfo) => {
      const step = AGENT_TO_STEP[agent.name];
      if (step) {
        handleResumeFromStep(step);
      }
    },
    [handleResumeFromStep]
  );

  const agentNames = [...new Set(agents.map((a) => a.name))];

  const runningCount = agents.filter((a) => a.status === "running").length;
  const completedCount = agents.filter((a) => a.status === "completed").length;
  const idleCount = agents.filter((a) => a.status === "idle").length;
  const errorCount = agents.filter((a) => a.status === "error").length;
  const allIdle = agents.every((a) => a.status === "idle");

  return (
    <RequireAuth>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8"
      >
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary to-secondary flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Agent Activity Dashboard
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Real-time orchestration monitoring &amp; live agent events
          </p>
        </div>

        <div className="flex items-center gap-3">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => window.location.reload()}
            className="p-2.5 rounded-xl glass border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 transition-all"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </motion.button>

          {/* Demo mode button */}
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={startDemo}
            disabled={isRunning}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:border-primary/30 disabled:opacity-40 transition-all"
            title="Preview a simulated agent run"
          >
            {isRunning && demoMode ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Simulating...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Demo
              </>
            )}
          </motion.button>

          {/* Real entry point */}
          <Link href="/company-finder">
            <motion.div
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="btn-futuristic flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm bg-linear-to-r from-primary to-secondary text-primary-foreground shadow-lg shadow-primary/20 cursor-pointer"
            >
              <Building2 className="w-4 h-4" />
              Run Company Finder
              <ArrowRight className="w-4 h-4" />
            </motion.div>
          </Link>
        </div>
      </motion.div>

      {/* Idle state info banner */}
      <AnimatePresence>
        {allIdle && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-start gap-3 px-4 py-3 mb-6 bg-primary/5 border border-primary/20 rounded-xl text-sm"
          >
            <Info className="w-4 h-4 text-primary mt-0.5 shrink-0" />
            <div>
              <p className="text-foreground font-medium">No agents running</p>
              <p className="text-muted-foreground text-xs mt-0.5">
                Click <strong>Run Company Finder</strong> to start the pipeline â€” the agent will discover companies, rank them by match score, and find contact emails.
                Or click <strong>Demo</strong> to preview a simulated run.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Status summary bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Running", count: runningCount, color: "text-emerald-500", bgGradient: "from-emerald-500/20 to-emerald-500/5", border: "border-emerald-500/30" },
          { label: "Completed", count: completedCount, color: "text-primary", bgGradient: "from-primary/20 to-primary/5", border: "border-primary/30" },
          { label: "Idle", count: idleCount, color: "text-amber-500", bgGradient: "from-amber-500/20 to-amber-500/5", border: "border-amber-500/30" },
          { label: "Error", count: errorCount, color: "text-red-500", bgGradient: "from-red-500/20 to-red-500/5", border: "border-red-500/30" },
        ].map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ scale: 1.02, y: -2 }}
            className={`glass border ${item.border} rounded-xl p-4 text-center relative overflow-hidden group`}
          >
            <div className={`absolute inset-0 bg-linear-to-br ${item.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
            <div className={`relative z-10 text-2xl font-bold ${item.color}`}>{item.count}</div>
            <div className="relative z-10 text-xs text-muted-foreground">{item.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Orchestration Flow */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass border border-border rounded-2xl p-6 mb-6"
      >
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Orchestration Flow
          </h2>
        </div>
        <OrchestrationFlow
          activeStep={activeStep}
          currentTask={runningAgent?.currentTask}
          onStepClick={handleResumeFromStep}
        />
      </motion.div>

      {/* Main panels */}
      <div className="grid lg:grid-cols-5 gap-6 mb-6">
        {/* Agent Cards */}
        <div className="lg:col-span-3">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-secondary" />
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Live Agent Status
            </h2>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {agents.map((agent, i) => (
              <AgentCard key={agent.name} agent={agent} index={i} onClick={handleAgentCardClick} />
            ))}
          </div>
        </div>

        {/* Event Stream */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Event Stream
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-3 h-3 text-muted-foreground" />
              <select
                value={filterAgent}
                onChange={(e) => setFilterAgent(e.target.value)}
                className="text-xs bg-card border border-border rounded-lg px-2 py-1.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
              >
                <option value="all">All agents</option>
                {agentNames.map((n) => (
                  <option key={n} value={n}>
                    {n.replace("Agent", "")}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div
            ref={logRef}
            className="glass border border-border rounded-2xl p-4 h-120 overflow-y-auto"
          >
            <AnimatePresence>
              {filteredEvents.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center h-full gap-3 text-center"
                >
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center opacity-40">
                    <Activity className="w-6 h-6 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">No events yet</p>
                  <p className="text-xs text-muted-foreground opacity-60">
                    Events will appear here when agents are running
                  </p>
                </motion.div>
              ) : (
                <EventStream events={filteredEvents} />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Task Timeline */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Task Timeline â€” Per Company
          </h2>
        </div>
        <TaskTimeline items={MOCK_PIPELINE} />
      </motion.div>
      </div>
    </RequireAuth>
  );
}

