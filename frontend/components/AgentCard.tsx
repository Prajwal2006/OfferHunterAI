"use client";

import { motion } from "framer-motion";
import { AgentInfo, AgentStatus } from "@/lib/types";

const statusConfig: Record<
  AgentStatus,
  { color: string; bg: string; border: string; dot: string; label: string; gradient: string }
> = {
  running: {
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    dot: "bg-emerald-500",
    label: "Running",
    gradient: "from-emerald-500/20 to-emerald-500/5",
  },
  idle: {
    color: "text-amber-500",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    dot: "bg-amber-500",
    label: "Idle",
    gradient: "from-amber-500/20 to-amber-500/5",
  },
  error: {
    color: "text-red-500",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    dot: "bg-red-500",
    label: "Error",
    gradient: "from-red-500/20 to-red-500/5",
  },
  completed: {
    color: "text-primary",
    bg: "bg-primary/10",
    border: "border-primary/30",
    dot: "bg-primary",
    label: "Completed",
    gradient: "from-primary/20 to-primary/5",
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
      whileHover={{ y: -4, scale: 1.01 }}
      className={`relative p-5 rounded-2xl border ${cfg.border} glass overflow-hidden group cursor-default`}
    >
      {/* Gradient background on hover */}
      <div className={`absolute inset-0 bg-gradient-to-br ${cfg.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />

      {/* Subtle glow for running agents */}
      {agent.status === "running" && (
        <div className="absolute inset-0 rounded-2xl bg-emerald-500/5 animate-pulse" />
      )}

      <div className="relative z-10 flex items-start gap-4">
        {/* Icon */}
        <div className="text-2xl w-12 h-12 flex items-center justify-center rounded-xl bg-muted/50 dark:bg-muted/30 border border-border group-hover:border-primary/30 transition-colors">
          {agent.icon}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-sm text-foreground truncate">
              {agent.displayName}
            </span>
            <div
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.border} border ${cfg.color}`}
            >
              <div
                className={`w-1.5 h-1.5 rounded-full ${cfg.dot} ${
                  agent.status === "running" ? "pulse-neon" : ""
                }`}
              />
              {cfg.label}
            </div>
          </div>

          <p className="text-xs text-muted-foreground mb-2">{agent.description}</p>

          {agent.currentTask && (
            <div className="flex items-center gap-2 text-xs">
              <div
                className={`w-1.5 h-1.5 rounded-full ${cfg.dot} flex-shrink-0`}
              />
              <span className={`${cfg.color} truncate font-medium`}>
                {agent.currentTask}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Running progress bar */}
      {agent.status === "running" && (
        <div className="relative z-10 mt-4 h-1 bg-muted/30 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full"
            initial={{ width: "0%" }}
            animate={{ width: "70%" }}
            transition={{ duration: 2, repeat: Infinity, repeatType: "reverse" }}
          />
        </div>
      )}
    </motion.div>
  );
}
