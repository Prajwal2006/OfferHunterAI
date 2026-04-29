"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Activity,
  Mail,
  GitBranch,
  Play,
  CheckCircle,
  Clock,
  TrendingUp,
  Zap,
  ChevronRight,
} from "lucide-react";
import { MOCK_AGENTS, MOCK_EVENTS, MOCK_COMPANIES, MOCK_EMAILS } from "@/lib/mockData";
import AgentCard from "@/components/AgentCard";

const stats = [
  {
    label: "Companies Discovered",
    value: "12",
    change: "+3 today",
    icon: TrendingUp,
    color: "text-cyan-400",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/30",
  },
  {
    label: "Emails Drafted",
    value: "8",
    change: "3 pending review",
    icon: Mail,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  {
    label: "Emails Sent",
    value: "3",
    change: "1 replied",
    icon: CheckCircle,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  {
    label: "Avg Response Rate",
    value: "33%",
    change: "Above average",
    icon: Activity,
    color: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
  },
];

export default function HomePage() {
  const [isRunning, setIsRunning] = useState(false);

  const pendingApprovals = MOCK_EMAILS.filter(
    (e) => e.status === "pending_approval"
  ).length;

  const recentEvents = MOCK_EVENTS.slice(-4).reverse();

  function handleStart() {
    setIsRunning(true);
    setTimeout(() => setIsRunning(false), 3000);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="text-blue-400 neon-blue">OfferHunter</span>{" "}
              <span className="text-purple-400 neon-purple">AI</span>
            </h1>
            <p className="text-slate-400 mt-1">
              Multi-agent job discovery &amp; outreach automation
            </p>
          </div>

          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleStart}
            disabled={isRunning}
            className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-lg shadow-blue-500/25 disabled:opacity-60 transition-all"
          >
            {isRunning ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Running Agents...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" fill="currentColor" />
                Run Agent Pipeline
              </>
            )}
          </motion.button>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 + 0.1 }}
              className={`glass border ${stat.border} rounded-xl p-4`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className={`p-2 rounded-lg ${stat.bg}`}>
                  <Icon className={`w-4 h-4 ${stat.color}`} />
                </div>
                <span className={`text-2xl font-bold ${stat.color}`}>
                  {stat.value}
                </span>
              </div>
              <div className="text-xs text-slate-400 font-medium">{stat.label}</div>
              <div className="text-xs text-slate-600 mt-0.5">{stat.change}</div>
            </motion.div>
          );
        })}
      </div>

      {/* Pending Approval Banner */}
      {pendingApprovals > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mb-6 p-4 rounded-xl border border-amber-500/40 bg-amber-500/10 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <div className="text-sm font-semibold text-amber-300">
                {pendingApprovals} email{pendingApprovals !== 1 ? "s" : ""} pending your approval
              </div>
              <div className="text-xs text-amber-600">
                Review and approve before sending — human-in-the-loop required
              </div>
            </div>
          </div>
          <Link href="/review">
            <motion.div
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="flex items-center gap-1 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 text-sm font-medium hover:bg-amber-500/30 transition-colors"
            >
              Review Now <ChevronRight className="w-4 h-4" />
            </motion.div>
          </Link>
        </motion.div>
      )}

      {/* Main grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Agent Status */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-400" />
              Agent Status
            </h2>
            <Link
              href="/agents"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
            >
              Full Dashboard <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            {MOCK_AGENTS.map((agent, i) => (
              <AgentCard key={agent.name} agent={agent} index={i} />
            ))}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Recent Events */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
                <Activity className="w-5 h-5 text-purple-400" />
                Live Events
              </h2>
              <Link
                href="/agents"
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
              >
                View All <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="glass border border-[var(--border-color)] rounded-xl p-4 space-y-2 font-mono text-xs">
              {recentEvents.map((event) => (
                <div key={event.id} className="flex gap-2 items-start">
                  <span className="text-slate-600 flex-shrink-0">
                    {new Date(event.created_at).toLocaleTimeString("en-US", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                      hour12: false,
                    })}
                  </span>
                  <span
                    className={`flex-shrink-0 ${
                      event.status === "completed"
                        ? "text-emerald-400"
                        : event.status === "running"
                        ? "text-blue-400"
                        : "text-amber-400"
                    }`}
                  >
                    [{event.agent_name.replace("Agent", "")}]
                  </span>
                  <span className="text-slate-400 truncate">{event.message}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <GitBranch className="w-5 h-5 text-emerald-400" />
              Quick Actions
            </h2>
            <div className="space-y-2">
              {[
                {
                  href: "/agents",
                  label: "Agent Activity Dashboard",
                  desc: "Real-time agent monitoring",
                  icon: "📡",
                },
                {
                  href: "/review",
                  label: "Review & Approve Emails",
                  desc: `${pendingApprovals} awaiting approval`,
                  icon: "✉️",
                },
                {
                  href: "/pipeline",
                  label: "Outreach Pipeline",
                  desc: `${MOCK_COMPANIES.length} companies tracked`,
                  icon: "📊",
                },
              ].map((item) => (
                <Link key={item.href} href={item.href}>
                  <motion.div
                    whileHover={{ x: 4 }}
                    className="flex items-center gap-3 p-3 rounded-lg glass border border-[var(--border-color)] hover:border-blue-500/30 transition-all cursor-pointer"
                  >
                    <span className="text-xl">{item.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-300">
                        {item.label}
                      </div>
                      <div className="text-xs text-slate-600">{item.desc}</div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-600 flex-shrink-0" />
                  </motion.div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
