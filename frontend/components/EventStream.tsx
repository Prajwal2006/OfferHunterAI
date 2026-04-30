"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { AgentEvent } from "@/lib/types";

const agentColors: Record<string, string> = {
  CompanyFinderAgent: "text-cyan-500",
  PersonalizationAgent: "text-secondary",
  EmailWriterAgent: "text-primary",
  ResumeTailorAgent: "text-indigo-500",
  EmailSenderAgent: "text-emerald-500",
  FollowUpAgent: "text-amber-500",
  ResponseClassifierAgent: "text-pink-500",
};

const statusIcons: Record<string, string> = {
  started: "▶",
  running: "⟳",
  completed: "✓",
  failed: "✗",
};

const statusColors: Record<string, string> = {
  started: "text-amber-500",
  running: "text-primary",
  completed: "text-emerald-500",
  failed: "text-red-500",
};

interface EventStreamProps {
  events: AgentEvent[];
}

function formatTime(isoString: string) {
  const date = new Date(isoString);
  // Use UTC-based formatting to avoid hydration mismatches
  const hours = date.getUTCHours().toString().padStart(2, "0");
  const minutes = date.getUTCMinutes().toString().padStart(2, "0");
  const seconds = date.getUTCSeconds().toString().padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

export default function EventStream({ events }: EventStreamProps) {
  return (
    <div className="font-mono text-xs space-y-1.5">
      {events.length === 0 && (
        <div className="text-muted-foreground text-center py-8">
          No events yet. Start an agent run to see logs.
        </div>
      )}
      {[...events].reverse().map((event, i) => {
        const agentColor = agentColors[event.agent_name] ?? "text-muted-foreground";
        const statusColor = statusColors[event.status] ?? "text-muted-foreground";
        const statusIcon = statusIcons[event.status] ?? "•";

        return (
          <motion.div
            key={event.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i < 5 ? 0 : 0 }}
            className="log-entry flex items-start gap-2 py-1.5 px-2 rounded-lg hover:bg-muted/50 transition-colors group"
          >
            {/* Timestamp */}
            <span className="text-muted-foreground flex-shrink-0 w-[60px]">
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
            <span className="text-foreground/70 group-hover:text-foreground transition-colors break-all">
              {event.message}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}
