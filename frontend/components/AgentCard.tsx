"use client";

import { motion } from "framer-motion";
import { AgentInfo, AgentStatus } from "@/lib/types";

const statusConfig: Record<
  AgentStatus,
  { color: string; bg: string; border: string; dot: string; label: string }
> = {
  running: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    dot: "bg-emerald-400",
    label: "Running",
  },
  idle: {
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    dot: "bg-amber-400",
    label: "Idle",
  },
  error: {
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    dot: "bg-red-400",
    label: "Error",
  },
  completed: {
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    dot: "bg-blue-400",
    label: "Completed",
  },
};

interface AgentCardProps {
  agent: AgentInfo;
  index: number;
}

export default function AgentCard({ agent, index }: AgentCardProps) {
  const cfg = statusConfig[agent.status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className={`agent-card relative p-4 rounded-xl border ${cfg.border} ${cfg.bg} glass`}
    >
      {/* Subtle glow for running agents */}
      {agent.status === "running" && (
        <div className="absolute inset-0 rounded-xl bg-emerald-500/5 animate-pulse" />
      )}

      <div className="relative flex items-start gap-3">
        {/* Icon */}
        <div className="text-2xl w-10 h-10 flex items-center justify-center rounded-lg bg-white/5">
          {agent.icon}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-semibold text-sm text-slate-200 truncate">
              {agent.displayName}
            </span>
            <div
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.border} border ${cfg.color}`}
            >
              <div
                className={`w-1.5 h-1.5 rounded-full ${cfg.dot} ${
                  agent.status === "running" ? "pulse-neon" : ""
                }`}
              />
              {cfg.label}
            </div>
          </div>

          <p className="text-xs text-slate-500 mb-2">{agent.description}</p>

          {agent.currentTask && (
            <div className="flex items-center gap-1.5 text-xs">
              <div
                className={`w-1 h-1 rounded-full ${cfg.dot} flex-shrink-0`}
              />
              <span className={`${cfg.color} truncate`}>
                {agent.currentTask}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Running progress bar */}
      {agent.status === "running" && (
        <div className="mt-3 h-0.5 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-emerald-400 rounded-full"
            initial={{ width: "0%" }}
            animate={{ width: "70%" }}
            transition={{ duration: 2, repeat: Infinity, repeatType: "reverse" }}
          />
        </div>
      )}
    </motion.div>
  );
}
