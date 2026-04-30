"use client";

import { motion } from "framer-motion";
import { PipelineItem } from "@/lib/types";

const agentColors: Record<string, string> = {
  CompanyFinder: "bg-cyan-500",
  Personalization: "bg-secondary",
  EmailWriter: "bg-primary",
  Review: "bg-amber-500",
  Sender: "bg-emerald-500",
};

const statusConfig = {
  completed: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-500", dot: "bg-emerald-500" },
  running: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-500", dot: "bg-amber-500" },
  pending: { bg: "bg-muted", border: "border-border", text: "text-muted-foreground", dot: "bg-muted-foreground" },
  failed: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-500", dot: "bg-red-500" },
};

interface TaskTimelineProps {
  items: PipelineItem[];
}

export default function TaskTimeline({ items }: TaskTimelineProps) {
  return (
    <div className="space-y-4">
      {items.map((item, itemIndex) => (
        <motion.div
          key={item.id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: itemIndex * 0.05 }}
          whileHover={{ scale: 1.01 }}
          className="glass border border-border rounded-2xl p-5 group"
        >
          {/* Company header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 border border-border flex items-center justify-center text-sm font-bold text-foreground">
                {item.company.name[0]}
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">
                  {item.company.name}
                </div>
                <div className="text-xs text-muted-foreground">{item.company.industry}</div>
              </div>
            </div>
            <div className="text-xs text-muted-foreground">
              Score: <span className="text-primary font-semibold">{Math.round(item.company.relevance_score * 100)}%</span>
            </div>
          </div>

          {/* Timeline */}
          <div className="flex items-center gap-1 overflow-x-auto">
            {item.steps.map((step, stepIndex) => {
              const cfg = statusConfig[step.status];
              const dotColor = agentColors[step.agent] ?? cfg.dot;

              return (
                <div key={step.agent} className="flex items-center gap-1 flex-1 min-w-0">
                  {/* Step block */}
                  <motion.div
                    whileHover={{ scale: 1.05, y: -2 }}
                    className={`relative flex-1 min-w-[80px] p-3 rounded-xl border text-center cursor-default transition-colors ${cfg.bg} ${cfg.border}`}
                    title={step.message}
                  >
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <div className={`w-2 h-2 rounded-full ${dotColor}`} />
                    </div>
                    <div className={`text-xs font-medium ${cfg.text} truncate`}>
                      {step.agent}
                    </div>
                    {step.timestamp && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(step.timestamp).toLocaleTimeString("en-US", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    )}
                  </motion.div>

                  {/* Connector */}
                  {stepIndex < item.steps.length - 1 && (
                    <div className="w-3 h-0.5 bg-border rounded-full flex-shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
