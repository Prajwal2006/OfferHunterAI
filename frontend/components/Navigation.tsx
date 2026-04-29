"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, LayoutDashboard, Mail, GitBranch, Zap } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/agents", label: "Agent Activity", icon: Activity },
  { href: "/review", label: "Review Emails", icon: Mail },
  { href: "/pipeline", label: "Pipeline", icon: GitBranch },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 glass border-b border-[var(--border-color)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="relative">
              <Zap
                className="w-7 h-7 text-blue-400 group-hover:text-purple-400 transition-colors"
                fill="currentColor"
              />
              <div className="absolute inset-0 blur-md text-blue-400 group-hover:text-purple-400 transition-colors opacity-50">
                <Zap className="w-7 h-7" fill="currentColor" />
              </div>
            </div>
            <span className="font-bold text-lg tracking-tight">
              <span className="text-blue-400">Offer</span>
              <span className="text-purple-400">Hunter</span>
              <span className="text-slate-300"> AI</span>
            </span>
          </Link>

          {/* Nav Links */}
          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link key={item.href} href={item.href}>
                  <motion.div
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="hidden sm:inline">{item.label}</span>
                  </motion.div>
                </Link>
              );
            })}
          </div>

          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30">
              <div className="w-2 h-2 rounded-full bg-emerald-400 pulse-neon" />
              <span className="text-xs text-emerald-400 font-medium">System Active</span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
