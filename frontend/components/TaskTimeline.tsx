"use client";

import { motion } from "framer-motion";
import { PipelineItem } from "@/lib/types";

const agentColors: Record<string, string> = {
  CompanyFinder: "bg-cyan-400",
  Personalization: "bg-purple-400",
  EmailWriter: "bg-blue-400",
  Review: "bg-amber-400",
  Sender: "bg-emerald-400",
};

const statusConfig = {
  completed: { bg: "bg-emerald-500/20", border: "border-emerald-500/40", text: "text-emerald-400", dot: "bg-emerald-400" },
  running: { bg: "bg-amber-500/20", border: "border-amber-500/40", text: "text-amber-400", dot: "bg-amber-400" },
  pending: { bg: "bg-slate-800", border: "border-slate-700", text: "text-slate-600", dot: "bg-slate-600" },
  failed: { bg: "bg-red-500/20", border: "border-red-500/40", text: "text-red-400", dot: "bg-red-400" },
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
          className="glass border border-[var(--border-color)] rounded-xl p-4"
        >
          {/* Company header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-sm font-bold text-slate-300">
                {item.company.name[0]}
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-200">
                  {item.company.name}
                </div>
                <div className="text-xs text-slate-500">{item.company.industry}</div>
              </div>
            </div>
            <div className="text-xs text-slate-500">
              Score: <span className="text-blue-400">{Math.round(item.company.relevance_score * 100)}%</span>
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
                    whileHover={{ scale: 1.05 }}
                    className={`relative flex-1 min-w-[80px] p-2 rounded-lg border text-center cursor-default ${cfg.bg} ${cfg.border}`}
                    title={step.message}
                  >
                    <div className="flex items-center justify-center gap-1 mb-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
                    </div>
                    <div className={`text-xs font-medium ${cfg.text} truncate`}>
                      {step.agent}
                    </div>
                    {step.timestamp && (
                      <div className="text-xs text-slate-600 mt-0.5">
                        {new Date(step.timestamp).toLocaleTimeString("en-US", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    )}
                  </motion.div>

                  {/* Connector */}
                  {stepIndex < item.steps.length - 1 && (
                    <div className="w-2 h-0.5 bg-slate-700 flex-shrink-0" />
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
