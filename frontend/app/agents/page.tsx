"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity, Play, RefreshCw, Filter } from "lucide-react";
import { AgentEvent, AgentInfo } from "@/lib/types";
import { MOCK_AGENTS, MOCK_EVENTS } from "@/lib/mockData";
import AgentCard from "@/components/AgentCard";
import EventStream from "@/components/EventStream";
import OrchestrationFlow from "@/components/OrchestrationFlow";
import TaskTimeline from "@/components/TaskTimeline";
import { MOCK_PIPELINE } from "@/lib/mockData";

function useSimulatedEvents(initial: AgentEvent[]) {
  const [events, setEvents] = useState<AgentEvent[]>(initial);
  const [agents, setAgents] = useState<AgentInfo[]>(MOCK_AGENTS);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const simulatedMessages = [
    { agent: "CompanyFinderAgent", msg: "Scanning LinkedIn for ML Engineer roles", status: "running" as const },
    { agent: "PersonalizationAgent", msg: "Extracting tech stack from Anthropic careers page", status: "running" as const },
    { agent: "EmailWriterAgent", msg: "Generating email draft for Anthropic", status: "running" as const },
    { agent: "ResumeTailorAgent", msg: "Tailoring resume bullets for AI/ML focus", status: "running" as const },
    { agent: "PersonalizationAgent", msg: "Completed analysis for Anthropic", status: "completed" as const },
    { agent: "EmailWriterAgent", msg: "Email draft complete for Anthropic — pending review", status: "completed" as const },
    { agent: "CompanyFinderAgent", msg: "Found 3 new companies: Cohere, Mistral, Together AI", status: "completed" as const },
    { agent: "FollowUpAgent", msg: "Checking response status for Supabase outreach", status: "running" as const },
    { agent: "ResponseClassifierAgent", msg: "No response detected — follow-up scheduled in 3 days", status: "completed" as const },
  ];

  function startSimulation() {
    if (isRunning) return;
    setIsRunning(true);

    let i = 0;
    intervalRef.current = setInterval(() => {
      if (i >= simulatedMessages.length) {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setIsRunning(false);
        return;
      }

      const sim = simulatedMessages[i];
      const newEvent: AgentEvent = {
        id: `sim-${Date.now()}-${i}`,
        agent_name: sim.agent,
        task_id: `task-sim-${i}`,
        status: sim.status,
        message: sim.msg,
        metadata: {},
        created_at: new Date().toISOString(),
      };

      setEvents((prev) => [...prev, newEvent]);

      // Update agent status
      setAgents((prev) =>
        prev.map((a) =>
          a.name === sim.agent
            ? {
                ...a,
                status:
                  sim.status === "running"
                    ? "running"
                    : sim.status === "completed"
                    ? "completed"
                    : "error",
                currentTask: sim.status === "running" ? sim.msg : a.currentTask,
              }
            : a
        )
      );

      i++;
    }, 1500);
  }

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { events, agents, isRunning, startSimulation };
}

export default function AgentsPage() {
  const { events, agents, isRunning, startSimulation } = useSimulatedEvents(MOCK_EVENTS);
  const [filterAgent, setFilterAgent] = useState<string>("all");
  const logRef = useRef<HTMLDivElement>(null);

  const activeAgent = agents.find((a) => a.status === "running");

  const filteredEvents =
    filterAgent === "all"
      ? events
      : events.filter((e) => e.agent_name === filterAgent);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = 0;
    }
  }, [events]);

  const agentNames = [...new Set(MOCK_EVENTS.map((e) => e.agent_name))];

  const runningCount = agents.filter((a) => a.status === "running").length;
  const completedCount = agents.filter((a) => a.status === "completed").length;
  const idleCount = agents.filter((a) => a.status === "idle").length;
  const errorCount = agents.filter((a) => a.status === "error").length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8"
      >
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Activity className="w-6 h-6 text-blue-400" />
            Agent Activity Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time orchestration monitoring &amp; live agent events
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => window.location.reload()}
            className="p-2 rounded-lg glass border border-[var(--border-color)] text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={startSimulation}
            disabled={isRunning}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all"
          >
            {isRunning ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Simulating...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" fill="currentColor" />
                Simulate Run
              </>
            )}
          </motion.button>
        </div>
      </motion.div>

      {/* Status summary bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Running", count: runningCount, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
          { label: "Completed", count: completedCount, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
          { label: "Idle", count: idleCount, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
          { label: "Error", count: errorCount, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
        ].map((item) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`glass border ${item.border} rounded-xl p-3 text-center`}
          >
            <div className={`text-2xl font-bold ${item.color}`}>{item.count}</div>
            <div className="text-xs text-slate-500">{item.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Orchestration Flow */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass border border-[var(--border-color)] rounded-xl p-6 mb-6"
      >
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Orchestration Flow
        </h2>
        <OrchestrationFlow
          activeStep={activeAgent?.name.replace("Agent", "") ?? "EmailWriter"}
          currentTask={activeAgent?.currentTask}
        />
      </motion.div>

      {/* Main panels */}
      <div className="grid lg:grid-cols-5 gap-6 mb-6">
        {/* Agent Cards — 3 cols */}
        <div className="lg:col-span-3">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Live Agent Status
          </h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {agents.map((agent, i) => (
              <AgentCard key={agent.name} agent={agent} index={i} />
            ))}
          </div>
        </div>

        {/* Event Stream — 2 cols */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
              Event Stream
            </h2>
            <div className="flex items-center gap-2">
              <Filter className="w-3 h-3 text-slate-500" />
              <select
                value={filterAgent}
                onChange={(e) => setFilterAgent(e.target.value)}
                className="text-xs bg-transparent border border-[var(--border-color)] rounded px-2 py-1 text-slate-400 focus:outline-none focus:border-blue-500/50"
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
            className="glass border border-[var(--border-color)] rounded-xl p-4 h-[480px] overflow-y-auto"
          >
            <AnimatePresence>
              <EventStream events={filteredEvents} />
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
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Task Timeline — Per Company
        </h2>
        <TaskTimeline items={MOCK_PIPELINE} />
      </motion.div>
    </div>
  );
}
