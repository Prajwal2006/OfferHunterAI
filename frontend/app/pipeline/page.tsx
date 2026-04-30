"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, ExternalLink, Search } from "lucide-react";
import { MOCK_COMPANIES } from "@/lib/mockData";
import { Company } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";

type StatusFilter = "all" | Company["status"];

const statusConfig: Record<Company["status"], { label: string; color: string; bg: string; border: string }> = {
  discovered: { label: "Discovered", color: "text-muted-foreground", bg: "bg-muted/50", border: "border-border" },
  personalized: { label: "Personalized", color: "text-cyan-500", bg: "bg-cyan-500/10", border: "border-cyan-500/30" },
  email_drafted: { label: "Email Drafted", color: "text-secondary", bg: "bg-secondary/10", border: "border-secondary/30" },
  pending_approval: { label: "Pending Review", color: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/30" },
  sent: { label: "Sent", color: "text-primary", bg: "bg-primary/10", border: "border-primary/30" },
  replied: { label: "Replied", color: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  followed_up: { label: "Followed Up", color: "text-indigo-500", bg: "bg-indigo-500/10", border: "border-indigo-500/30" },
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
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
              <GitBranch className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              Outreach Pipeline
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            CRM-style tracking for all company outreach
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-xl overflow-hidden border border-border glass">
            {(["board", "list"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-4 py-2 text-xs font-medium transition-colors ${
                  view === v
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search companies..."
              className="pl-9 pr-4 py-2 text-sm bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 w-48 transition-all"
            />
          </div>
        </div>
      </motion.div>

      {/* Stats summary */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-8">
        {pipelineColumns.map((col, i) => {
          const count = MOCK_COMPANIES.filter((c) => c.status === col.id).length;
          const cfg = statusConfig[col.id];
          return (
            <motion.div
              key={col.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              whileHover={{ scale: 1.03, y: -2 }}
              className={`glass border ${statusFilter === col.id ? "border-primary" : "border-border"} rounded-xl p-3 text-center cursor-pointer transition-all`}
              onClick={() => setStatusFilter(statusFilter === col.id ? "all" : col.id)}
            >
              <div className="text-xl mb-1">{col.icon}</div>
              <div className={`text-xl font-bold ${cfg.color}`}>{count}</div>
              <div className="text-xs text-muted-foreground truncate">{col.label}</div>
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
                <div className={`flex items-center gap-2 px-4 py-3 rounded-t-xl border-t border-x ${cfg.border} ${cfg.bg}`}>
                  <span>{col.icon}</span>
                  <span className={`text-sm font-semibold ${cfg.color}`}>
                    {col.label}
                  </span>
                  <span className={`ml-auto text-xs ${cfg.color} opacity-70`}>
                    {companies.length}
                  </span>
                </div>
                <div className={`border-b border-x ${cfg.border} rounded-b-xl min-h-[200px] p-3 space-y-3 bg-card/50`}>
                  {companies.map((company, i) => (
                    <motion.div
                      key={company.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.05 }}
                      whileHover={{ scale: 1.02, y: -2 }}
                      className="glass border border-border rounded-xl p-4 hover:border-primary/30 transition-all cursor-default"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-foreground truncate">
                            {company.name}
                          </div>
                          <div className="text-xs text-muted-foreground truncate mt-0.5">
                            {company.industry}
                          </div>
                        </div>
                        <a
                          href={`https://${company.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-muted-foreground hover:text-primary transition-colors flex-shrink-0"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                      <div className="mt-3 flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">{company.size}</span>
                        <span className={`text-xs font-semibold ${cfg.color}`}>
                          {Math.round(company.relevance_score * 100)}% match
                        </span>
                      </div>
                    </motion.div>
                  ))}
                  {companies.length === 0 && (
                    <div className="text-xs text-muted-foreground text-center py-8">
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
        <div className="glass border border-border rounded-2xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider px-4 py-4">
                  Company
                </th>
                <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider px-4 py-4 hidden sm:table-cell">
                  Industry
                </th>
                <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider px-4 py-4 hidden md:table-cell">
                  Size
                </th>
                <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider px-4 py-4">
                  Status
                </th>
                <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider px-4 py-4 hidden sm:table-cell">
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
                    className="border-b border-border hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 border border-border flex items-center justify-center text-sm font-bold text-foreground flex-shrink-0">
                          {company.name[0]}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-foreground">
                            {company.name}
                          </div>
                          <div className="text-xs text-muted-foreground">{company.domain}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 hidden sm:table-cell">
                      <span className="text-sm text-muted-foreground">{company.industry}</span>
                    </td>
                    <td className="px-4 py-4 hidden md:table-cell">
                      <span className="text-sm text-muted-foreground">{company.size}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`px-3 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.border} ${cfg.color}`}
                      >
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-4 py-4 hidden sm:table-cell">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-muted rounded-full max-w-[60px]">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{ width: `${company.relevance_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
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
            <div className="text-center py-12 text-muted-foreground">
              No companies match your filter
            </div>
          )}
        </div>
      )}
      </div>
    </RequireAuth>
  );
}
