"use client";

import { motion } from "framer-motion";
import {
  ExternalLink,
  MapPin,
  Users,
  Briefcase,
  Wifi,
  WifiOff,
  Globe,
  Sparkles,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Company } from "@/lib/types";

interface CompanyCardProps {
  company: Company;
  index: number;
  onClick: (company: Company) => void;
}

function MatchBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, delay: 0.2 }}
        />
      </div>
      <span className="text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

function HiringBadge({ status }: { status?: string }) {
  if (status === "actively_hiring") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-500/15 text-green-600 dark:text-green-400 border border-green-500/25">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        Actively Hiring
      </span>
    );
  }
  if (status === "hiring") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/25">
        Hiring
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-muted text-muted-foreground border border-border">
      Unknown
    </span>
  );
}

export default function CompanyCard({ company, index, onClick }: CompanyCardProps) {
  const ranking = company.ranking;
  const matchScore = ranking?.match_score ?? company.match_score ?? company.relevance_score ?? 0;
  const matchPct = Math.round(matchScore * 100);

  const ringColor =
    matchPct >= 80
      ? "ring-green-500/40"
      : matchPct >= 60
      ? "ring-yellow-500/40"
      : "ring-border";

  const scoreColor =
    matchPct >= 80
      ? "text-green-500"
      : matchPct >= 60
      ? "text-yellow-500"
      : "text-muted-foreground";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      onClick={() => onClick(company)}
      className={`glass border border-border ${ringColor} ring-1 rounded-2xl p-5 cursor-pointer
        hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5 transition-all group`}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        {/* Logo */}
        <div className="w-12 h-12 rounded-xl bg-muted border border-border flex items-center justify-center shrink-0 overflow-hidden">
          {company.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={company.logo_url}
              alt={`${company.name} logo`}
              className="w-full h-full object-contain"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <span className="text-lg font-bold text-muted-foreground">
              {company.name.charAt(0)}
            </span>
          )}
        </div>

        {/* Company name + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-foreground text-base truncate">
              {company.name}
            </h3>
            <HiringBadge status={company.hiring_status} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-muted-foreground">
            {company.industry && (
              <span className="flex items-center gap-1">
                <Briefcase className="w-3 h-3" />
                {company.industry}
              </span>
            )}
            {company.headquarters && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {company.headquarters}
              </span>
            )}
            {company.size && (
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {company.size}
              </span>
            )}
            {company.remote_friendly !== undefined && (
              <span className="flex items-center gap-1">
                {company.remote_friendly ? (
                  <>
                    <Wifi className="w-3 h-3 text-green-500" />
                    <span className="text-green-500">Remote</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-3 h-3" />
                    Onsite
                  </>
                )}
              </span>
            )}
            {company.funding_stage && (
              <span className="flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-yellow-500" />
                {company.funding_stage}
              </span>
            )}
          </div>
        </div>

        {/* Match Score */}
        <div className="flex flex-col items-center shrink-0">
          <span className={`text-2xl font-black ${scoreColor}`}>{matchPct}</span>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            Match
          </span>
        </div>
      </div>

      {/* Description */}
      {company.description && (
        <p className="text-xs text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
          {company.description}
        </p>
      )}

      {/* Tech stack */}
      {company.tech_stack && company.tech_stack.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {company.tech_stack.slice(0, 5).map((tech) => (
            <span
              key={tech}
              className="px-2 py-0.5 rounded-md text-[10px] bg-primary/10 text-primary border border-primary/20"
            >
              {tech}
            </span>
          ))}
          {company.tech_stack.length > 5 && (
            <span className="px-2 py-0.5 rounded-md text-[10px] bg-muted text-muted-foreground">
              +{company.tech_stack.length - 5}
            </span>
          )}
        </div>
      )}

      {/* Score Breakdown */}
      {ranking && (
        <div className="space-y-1.5 mb-3 border-t border-border pt-3">
          <MatchBar score={ranking.skills_match} label="Skills" />
          <MatchBar score={ranking.tech_stack_match} label="Tech Stack" />
          <MatchBar score={ranking.interests_match} label="Domain" />
          <MatchBar score={ranking.hiring_likelihood} label="Hiring" />
        </div>
      )}

      {/* Strengths / Gaps */}
      {ranking && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {ranking.strengths.slice(0, 2).map((s) => (
            <span
              key={s}
              className="flex items-center gap-1 text-[10px] text-green-600 dark:text-green-400"
            >
              <CheckCircle2 className="w-3 h-3" />
              {s}
            </span>
          ))}
          {ranking.gaps.slice(0, 1).map((g) => (
            <span
              key={g}
              className="flex items-center gap-1 text-[10px] text-yellow-600 dark:text-yellow-400"
            >
              <AlertCircle className="w-3 h-3" />
              {g}
            </span>
          ))}
        </div>
      )}

      {/* Open positions count */}
      {company.open_positions && company.open_positions.length > 0 && (
        <div className="text-xs text-muted-foreground mb-3">
          <Briefcase className="inline w-3 h-3 mr-1" />
          {company.open_positions.length} open position
          {company.open_positions.length > 1 ? "s" : ""}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-border">
        <div className="flex items-center gap-2">
          {company.website_url && (
            <a
              href={company.website_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-primary transition-colors"
            >
              <Globe className="w-4 h-4" />
            </a>
          )}
          {company.linkedin_url && (
            <a
              href={company.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted-foreground hover:text-primary transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
        </div>

        <span className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-primary transition-colors">
          View details
          <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
        </span>
      </div>
    </motion.div>
  );
}
