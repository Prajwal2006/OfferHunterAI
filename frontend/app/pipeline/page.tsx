"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, ExternalLink, Search } from "lucide-react";
import { MOCK_COMPANIES } from "@/lib/mockData";
import { Company } from "@/lib/types";

type StatusFilter = "all" | Company["status"];

const statusConfig: Record<Company["status"], { label: string; color: string; bg: string; border: string }> = {
  discovered: { label: "Discovered", color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/30" },
  personalized: { label: "Personalized", color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/30" },
  email_drafted: { label: "Email Drafted", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30" },
  pending_approval: { label: "Pending Review", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
  sent: { label: "Sent", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
  replied: { label: "Replied", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  followed_up: { label: "Followed Up", color: "text-indigo-400", bg: "bg-indigo-500/10", border: "border-indigo-500/30" },
};

const pipelineColumns: { id: Company["status"]; label: string; icon: string }[] = [
  { id: "discovered", label: "Discovered", icon: "🔍" },
  { id: "personalized", label: "Personalized", icon: "🎯" },
  { id: "email_drafted", label: "Drafted", icon: "✍️" },
  { id: "pending_approval", label: "In Review", icon: "⏳" },
  { id: "sent", label: "Sent", icon: "📧" },
  { id: "replied", label: "Replied", icon: "💬" },
];

export default function PipelinePage() {
  const [view, setView] = useState<"board" | "list">("board");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const filtered = MOCK_COMPANIES.filter((c) => {
    const matchesSearch =
      search === "" ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.industry.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

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
            <GitBranch className="w-6 h-6 text-emerald-400" />
            Outreach Pipeline
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            CRM-style tracking for all company outreach
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-lg overflow-hidden border border-[var(--border-color)]">
            {(["board", "list"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === v
                    ? "bg-blue-500/20 text-blue-300"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search companies..."
              className="pl-8 pr-3 py-1.5 text-xs bg-transparent border border-[var(--border-color)] rounded-lg text-slate-400 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 w-48"
            />
          </div>
        </div>
      </motion.div>

      {/* Stats summary */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-8">
        {pipelineColumns.map((col) => {
          const count = MOCK_COMPANIES.filter((c) => c.status === col.id).length;
          const cfg = statusConfig[col.id];
          return (
            <motion.div
              key={col.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`glass border ${cfg.border} rounded-xl p-3 text-center cursor-pointer hover:scale-105 transition-transform`}
              onClick={() => setStatusFilter(statusFilter === col.id ? "all" : col.id)}
            >
              <div className="text-xl mb-1">{col.icon}</div>
              <div className={`text-xl font-bold ${cfg.color}`}>{count}</div>
              <div className="text-xs text-slate-500 truncate">{col.label}</div>
            </motion.div>
          );
        })}
      </div>

      {/* Board view */}
      {view === "board" && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {pipelineColumns.map((col) => {
            const companies = filtered.filter((c) => c.status === col.id);
            const cfg = statusConfig[col.id];

            return (
              <div
                key={col.id}
                className="flex-shrink-0 w-64"
              >
                <div className={`flex items-center gap-2 px-3 py-2 rounded-t-xl border-t border-x ${cfg.border} ${cfg.bg}`}>
                  <span>{col.icon}</span>
                  <span className={`text-sm font-semibold ${cfg.color}`}>
                    {col.label}
                  </span>
                  <span className={`ml-auto text-xs ${cfg.color} opacity-70`}>
                    {companies.length}
                  </span>
                </div>
                <div className={`border-b border-x ${cfg.border} rounded-b-xl min-h-[200px] p-2 space-y-2 bg-black/40`}>
                  {companies.map((company, i) => (
                    <motion.div
                      key={company.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="glass border border-[var(--border-color)] rounded-lg p-3 hover:border-blue-500/30 transition-colors cursor-default"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-slate-200 truncate">
                            {company.name}
                          </div>
                          <div className="text-xs text-slate-500 truncate mt-0.5">
                            {company.industry}
                          </div>
                        </div>
                        <a
                          href={`https://${company.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-600 hover:text-blue-400 transition-colors flex-shrink-0"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-xs text-slate-600">{company.size}</span>
                        <span className={`text-xs font-medium ${cfg.color}`}>
                          {Math.round(company.relevance_score * 100)}% match
                        </span>
                      </div>
                    </motion.div>
                  ))}
                  {companies.length === 0 && (
                    <div className="text-xs text-slate-700 text-center py-8">
                      No companies
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* List view */}
      {view === "list" && (
        <div className="glass border border-[var(--border-color)] rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border-color)]">
                <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Company
                </th>
                <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider px-4 py-3 hidden sm:table-cell">
                  Industry
                </th>
                <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider px-4 py-3 hidden md:table-cell">
                  Size
                </th>
                <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Status
                </th>
                <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider px-4 py-3 hidden sm:table-cell">
                  Match
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((company, i) => {
                const cfg = statusConfig[company.status];

                return (
                  <motion.tr
                    key={company.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="border-b border-[var(--border-color)] hover:bg-white/5 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-sm font-bold text-slate-300 flex-shrink-0">
                          {company.name[0]}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-slate-200">
                            {company.name}
                          </div>
                          <div className="text-xs text-slate-600">{company.domain}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <span className="text-sm text-slate-400">{company.industry}</span>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      <span className="text-sm text-slate-500">{company.size}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.border} ${cfg.color}`}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-slate-800 rounded-full max-w-[60px]">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${company.relevance_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-400">
                          {Math.round(company.relevance_score * 100)}%
                        </span>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="text-center py-12 text-slate-600">
              No companies match your filter
            </div>
          )}
        </div>
      )}
    </div>
  );
}
