"use client";

import { motion } from "framer-motion";
import { AgentEvent } from "@/lib/types";

const agentColors: Record<string, string> = {
  CompanyFinderAgent: "text-cyan-400",
  PersonalizationAgent: "text-purple-400",
  EmailWriterAgent: "text-blue-400",
  ResumeTailorAgent: "text-indigo-400",
  EmailSenderAgent: "text-emerald-400",
  FollowUpAgent: "text-amber-400",
  ResponseClassifierAgent: "text-pink-400",
};

const statusIcons: Record<string, string> = {
  started: "▶",
  running: "⟳",
  completed: "✓",
  failed: "✗",
};

const statusColors: Record<string, string> = {
  started: "text-amber-400",
  running: "text-blue-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
};

interface EventStreamProps {
  events: AgentEvent[];
}

function formatTime(isoString: string) {
  const date = new Date(isoString);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function EventStream({ events }: EventStreamProps) {
  return (
    <div className="font-mono text-xs space-y-1.5">
      {events.length === 0 && (
        <div className="text-slate-600 text-center py-8">
          No events yet. Start an agent run to see logs.
        </div>
      )}
      {[...events].reverse().map((event, i) => {
        const agentColor = agentColors[event.agent_name] ?? "text-slate-400";
        const statusColor = statusColors[event.status] ?? "text-slate-400";
        const statusIcon = statusIcons[event.status] ?? "•";

        return (
          <motion.div
            key={event.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i < 5 ? 0 : 0 }}
            className="log-entry flex items-start gap-2 py-1 px-2 rounded hover:bg-white/5 transition-colors group"
          >
            {/* Timestamp */}
            <span className="text-slate-600 flex-shrink-0 w-[60px]">
              {formatTime(event.created_at)}
            </span>

            {/* Status icon */}
            <span className={`flex-shrink-0 w-4 ${statusColor}`}>
              {statusIcon}
            </span>

            {/* Agent name */}
            <span className={`flex-shrink-0 ${agentColor} font-semibold`}>
              [{event.agent_name.replace("Agent", "")}]
            </span>

            {/* Message */}
            <span className="text-slate-300 break-all">{event.message}</span>
          </motion.div>
        );
      })}
    </div>
  );
}
