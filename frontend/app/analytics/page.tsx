"use client";

import { motion } from "framer-motion";
import {
  BarChart3,
  TrendingUp,
  Mail,
  Building2,
  Users,
  Clock,
  ArrowUp,
  ArrowDown,
  Activity,
  Target,
  Zap,
} from "lucide-react";

// Mock analytics data
const stats = [
  {
    label: "Emails Sent",
    value: 47,
    change: +12,
    icon: <Mail className="w-5 h-5" />,
    color: "text-primary",
    gradient: "from-primary/20 to-primary/5",
  },
  {
    label: "Companies Found",
    value: 156,
    change: +28,
    icon: <Building2 className="w-5 h-5" />,
    color: "text-cyan-500",
    gradient: "from-cyan-500/20 to-cyan-500/5",
  },
  {
    label: "Response Rate",
    value: "32%",
    change: +5,
    icon: <TrendingUp className="w-5 h-5" />,
    color: "text-emerald-500",
    gradient: "from-emerald-500/20 to-emerald-500/5",
  },
  {
    label: "Avg Response Time",
    value: "2.4d",
    change: -0.8,
    icon: <Clock className="w-5 h-5" />,
    color: "text-amber-500",
    gradient: "from-amber-500/20 to-amber-500/5",
  },
];

const weeklyData = [
  { day: "Mon", sent: 8, replies: 2 },
  { day: "Tue", sent: 12, replies: 4 },
  { day: "Wed", sent: 6, replies: 2 },
  { day: "Thu", sent: 9, replies: 3 },
  { day: "Fri", sent: 7, replies: 3 },
  { day: "Sat", sent: 3, replies: 1 },
  { day: "Sun", sent: 2, replies: 0 },
];

const topCompanies = [
  { name: "Anthropic", industry: "AI", score: 95, status: "Replied" },
  { name: "OpenAI", industry: "AI", score: 92, status: "Sent" },
  { name: "Stripe", industry: "Fintech", score: 88, status: "Replied" },
  { name: "Vercel", industry: "DevTools", score: 85, status: "Sent" },
  { name: "Linear", industry: "Productivity", score: 82, status: "Pending" },
];

const agentMetrics = [
  { name: "Company Finder", runs: 24, avgTime: "1.2s", success: 98 },
  { name: "Personalization", runs: 156, avgTime: "3.4s", success: 95 },
  { name: "Email Writer", runs: 47, avgTime: "2.8s", success: 100 },
  { name: "Follow-up", runs: 12, avgTime: "0.8s", success: 100 },
];

export default function AnalyticsPage() {
  const maxSent = Math.max(...weeklyData.map((d) => d.sent));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Track your job search performance and agent metrics
        </p>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ scale: 1.02, y: -4 }}
            className="glass border border-border rounded-2xl p-5 relative overflow-hidden group"
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} opacity-0 group-hover:opacity-100 transition-opacity`} />
            <div className="relative z-10">
              <div className={`w-10 h-10 rounded-xl ${stat.color} bg-current/20 flex items-center justify-center mb-4`}>
                <div className={stat.color}>{stat.icon}</div>
              </div>
              <div className="text-2xl font-bold text-foreground mb-1">{stat.value}</div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{stat.label}</span>
                <span className={`flex items-center gap-0.5 text-xs font-medium ${
                  stat.change > 0 ? "text-emerald-500" : "text-red-500"
                }`}>
                  {stat.change > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                  {Math.abs(stat.change)}%
                </span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        {/* Weekly Activity Chart */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass border border-border rounded-2xl p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
                Weekly Activity
              </h2>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-primary" />
                <span className="text-muted-foreground">Sent</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-muted-foreground">Replies</span>
              </div>
            </div>
          </div>

          <div className="flex items-end justify-between gap-2 h-40">
            {weeklyData.map((day, i) => (
              <div key={day.day} className="flex-1 flex flex-col items-center gap-2">
                <div className="w-full flex flex-col items-center gap-1 flex-1 justify-end">
                  {/* Sent bar */}
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${(day.sent / maxSent) * 100}%` }}
                    transition={{ delay: i * 0.05, duration: 0.5 }}
                    className="w-full max-w-[24px] bg-gradient-to-t from-primary to-primary/60 rounded-t-md relative group"
                  >
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 px-2 py-1 rounded bg-card border border-border text-xs text-foreground opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {day.sent} sent
                    </div>
                  </motion.div>
                  {/* Replies bar */}
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${(day.replies / maxSent) * 100}%` }}
                    transition={{ delay: i * 0.05 + 0.1, duration: 0.5 }}
                    className="w-full max-w-[16px] bg-gradient-to-t from-emerald-500 to-emerald-500/60 rounded-t-md"
                  />
                </div>
                <span className="text-xs text-muted-foreground">{day.day}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Top Companies */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass border border-border rounded-2xl p-6"
        >
          <div className="flex items-center gap-2 mb-6">
            <Target className="w-4 h-4 text-secondary" />
            <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Top Matched Companies
            </h2>
          </div>

          <div className="space-y-3">
            {topCompanies.map((company, i) => (
              <motion.div
                key={company.name}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.05 }}
                className="flex items-center gap-3 p-3 rounded-xl bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary/20 to-secondary/20 border border-border flex items-center justify-center text-sm font-bold text-foreground">
                  {company.name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground">{company.name}</div>
                  <div className="text-xs text-muted-foreground">{company.industry}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-primary">{company.score}%</div>
                  <div className={`text-xs ${
                    company.status === "Replied" ? "text-emerald-500" :
                    company.status === "Sent" ? "text-primary" : "text-amber-500"
                  }`}>
                    {company.status}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Agent Performance */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass border border-border rounded-2xl p-6"
      >
        <div className="flex items-center gap-2 mb-6">
          <Zap className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
            Agent Performance
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {agentMetrics.map((agent, i) => (
            <motion.div
              key={agent.name}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4 + i * 0.05 }}
              whileHover={{ scale: 1.02 }}
              className="p-4 rounded-xl bg-muted/30 border border-border hover:border-primary/30 transition-all"
            >
              <div className="text-sm font-semibold text-foreground mb-3">{agent.name}</div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-lg font-bold text-primary">{agent.runs}</div>
                  <div className="text-xs text-muted-foreground">Runs</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-secondary">{agent.avgTime}</div>
                  <div className="text-xs text-muted-foreground">Avg Time</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-emerald-500">{agent.success}%</div>
                  <div className="text-xs text-muted-foreground">Success</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Insights */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="mt-8 glass border border-primary/30 rounded-2xl p-6 bg-gradient-to-br from-primary/10 to-secondary/5"
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-1">AI-Powered Insights</h3>
            <p className="text-sm text-muted-foreground">
              Your response rate is <span className="text-emerald-500 font-semibold">32%</span> — 
              that&apos;s <span className="text-emerald-500 font-semibold">4x higher</span> than the industry average of 8%. 
              Companies in the <span className="text-primary font-semibold">AI/ML sector</span> show the highest engagement. 
              Consider focusing more outreach on similar companies.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
