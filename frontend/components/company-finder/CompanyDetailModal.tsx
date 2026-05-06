"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Globe,
  MapPin,
  Users,
  Briefcase,
  Wifi,
  ExternalLink,
  Mail,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Send,
  FileText,
  BarChart3,
  Target,
  Building2,
} from "lucide-react";

const LinkedinIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
);
import { Company, CompanyContact, JobPosition } from "@/lib/types";

interface CompanyDetailModalProps {
  company: Company;
  onClose: () => void;
  onHandoff: (
    companyId: string,
    agent: "email-writer" | "resume-tailor" | "personalizer"
  ) => void;
}

function ScoreBar({
  label,
  score,
  icon: Icon,
}: {
  label: string;
  score: number;
  icon: React.ElementType;
}) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium">{pct}%</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full ${color}`}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.5, delay: 0.1 }}
          />
        </div>
      </div>
    </div>
  );
}

function ContactRow({ contact }: { contact: CompanyContact }) {
  const typeColors: Record<string, string> = {
    recruiter: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
    founder: "bg-purple-500/15 text-purple-600 dark:text-purple-400",
    hiring_manager: "bg-green-500/15 text-green-600 dark:text-green-400",
    engineer: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
    hr: "bg-pink-500/15 text-pink-600 dark:text-pink-400",
    other: "bg-muted text-muted-foreground",
  };

  return (
    <div className="flex items-center gap-3 py-2 border-b border-border last:border-0">
      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-semibold text-muted-foreground shrink-0">
        {contact.name ? contact.name[0].toUpperCase() : "?"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-foreground">
            {contact.name || "Unknown"}
          </span>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded-md ${typeColors[contact.contact_type] || typeColors.other}`}
          >
            {contact.contact_type.replace(/_/g, " ")}
          </span>
          {contact.verified && (
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
          )}
        </div>
        {contact.title && (
          <p className="text-xs text-muted-foreground">{contact.title}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {contact.email && (
          <a
            href={`mailto:${contact.email}`}
            className="text-muted-foreground hover:text-primary transition-colors"
            title={contact.email}
          >
            <Mail className="w-4 h-4" />
          </a>
        )}
        {contact.linkedin_url && (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-primary transition-colors"
          >
            <LinkedinIcon className="w-4 h-4" />
          </a>
        )}
        <span className="text-[10px] text-muted-foreground">
          {Math.round((contact.confidence ?? 0) * 100)}%
        </span>
      </div>
    </div>
  );
}

function JobRow({ job }: { job: JobPosition }) {
  return (
    <a
      href={job.url || "#"}
      target={job.url ? "_blank" : undefined}
      rel="noopener noreferrer"
      className="flex items-center gap-3 py-2 border-b border-border last:border-0 hover:bg-muted/30 rounded-lg px-2 -mx-2 transition-colors group"
    >
      <Briefcase className="w-4 h-4 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground group-hover:text-primary transition-colors truncate">
          {job.title}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground mt-0.5">
          {job.location && <span>{job.location}</span>}
          {job.work_mode && <span className="capitalize">{job.work_mode}</span>}
          {job.salary_range && <span>{job.salary_range}</span>}
          {job.posted_at && <span>{job.posted_at}</span>}
        </div>
      </div>
      {job.url && <ExternalLink className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
    </a>
  );
}

export default function CompanyDetailModal({
  company,
  onClose,
  onHandoff,
}: CompanyDetailModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const ranking = company.ranking;
  const matchPct = Math.round(
    (ranking?.match_score ?? company.match_score ?? company.relevance_score ?? 0) * 100
  );
  const contacts = company.company_contacts ?? company.contacts ?? [];
  const jobs = company.open_positions ?? [];

  // Close on backdrop click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

        {/* Modal */}
        <motion.div
          ref={modalRef}
          className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto glass border border-border rounded-2xl shadow-2xl"
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="p-6">
            {/* Header */}
            <div className="flex items-start gap-4 mb-6">
              <div className="w-16 h-16 rounded-2xl bg-muted border border-border flex items-center justify-center overflow-hidden shrink-0">
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
                  <Building2 className="w-7 h-7 text-muted-foreground" />
                )}
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-xl font-bold text-foreground">{company.name}</h2>
                  {company.hiring_status === "actively_hiring" && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-500/15 text-green-600 dark:text-green-400 border border-green-500/25">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                      Actively Hiring
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-muted-foreground">
                  {company.industry && (
                    <span className="flex items-center gap-1">
                      <Briefcase className="w-3.5 h-3.5" />
                      {company.industry}
                    </span>
                  )}
                  {company.headquarters && (
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {company.headquarters}
                    </span>
                  )}
                  {company.size && (
                    <span className="flex items-center gap-1">
                      <Users className="w-3.5 h-3.5" />
                      {company.size} employees
                    </span>
                  )}
                  {company.founded_year && (
                    <span>Founded {company.founded_year}</span>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 mt-2">
                  {company.website_url && (
                    <a
                      href={company.website_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Globe className="w-3.5 h-3.5" />
                      Website
                    </a>
                  )}
                  {company.linkedin_url && (
                    <a
                      href={company.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <LinkedinIcon className="w-3.5 h-3.5" />
                      LinkedIn
                    </a>
                  )}
                  {company.remote_friendly && (
                    <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                      <Wifi className="w-3.5 h-3.5" />
                      Remote-friendly
                    </span>
                  )}
                  {company.sponsorship_available && (
                    <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
                      <Sparkles className="w-3.5 h-3.5" />
                      Sponsors visas
                    </span>
                  )}
                </div>
              </div>

              {/* Match Score Ring */}
              <div className="flex flex-col items-center shrink-0 bg-primary/5 border border-primary/20 rounded-xl px-4 py-3">
                <span
                  className={`text-3xl font-black ${
                    matchPct >= 75
                      ? "text-green-500"
                      : matchPct >= 50
                      ? "text-yellow-500"
                      : "text-muted-foreground"
                  }`}
                >
                  {matchPct}%
                </span>
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  Match
                </span>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Left column */}
              <div className="space-y-5">
                {/* Company Overview */}
                {(company.description || company.mission) && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Building2 className="w-4 h-4 text-primary" />
                      Overview
                    </h3>
                    {company.description && (
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {company.description}
                      </p>
                    )}
                    {company.mission && company.mission !== company.description && (
                      <p className="text-sm text-muted-foreground leading-relaxed mt-1 italic">
                        "{company.mission}"
                      </p>
                    )}
                  </section>
                )}

                {/* Tech Stack */}
                {company.tech_stack && company.tech_stack.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2">
                      Tech Stack
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {company.tech_stack.map((tech) => (
                        <span
                          key={tech}
                          className="px-2 py-0.5 rounded-md text-xs bg-primary/10 text-primary border border-primary/20"
                        >
                          {tech}
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                {/* Funding / Stage */}
                {company.funding_stage && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2">
                      Funding Stage
                    </h3>
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-yellow-500/15 text-yellow-700 dark:text-yellow-400 border border-yellow-500/25">
                      <Sparkles className="w-3.5 h-3.5" />
                      {company.funding_stage}
                    </span>
                  </section>
                )}

                {/* Culture Tags */}
                {company.culture_tags && company.culture_tags.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2">
                      Culture
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {company.culture_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 rounded-md text-xs bg-muted text-muted-foreground border border-border"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                {/* Open Positions */}
                {jobs.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Briefcase className="w-4 h-4 text-primary" />
                      Open Positions ({jobs.length})
                    </h3>
                    <div>
                      {jobs.map((job, i) => (
                        <JobRow key={i} job={job} />
                      ))}
                    </div>
                  </section>
                )}
              </div>

              {/* Right column */}
              <div className="space-y-5">
                {/* Match Breakdown */}
                {ranking && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-primary" />
                      Match Breakdown
                    </h3>
                    <div className="space-y-3">
                      <ScoreBar label="Skills" score={ranking.skills_match} icon={Target} />
                      <ScoreBar label="Tech Stack" score={ranking.tech_stack_match} icon={Target} />
                      <ScoreBar label="Domain" score={ranking.interests_match} icon={Briefcase} />
                      <ScoreBar label="Location" score={ranking.location_match} icon={MapPin} />
                      <ScoreBar label="Compensation" score={ranking.compensation_match} icon={Sparkles} />
                      <ScoreBar label="Hiring" score={ranking.hiring_likelihood} icon={Users} />
                      {ranking.visa_compatibility < 1 && (
                        <ScoreBar label="Visa" score={ranking.visa_compatibility} icon={CheckCircle2} />
                      )}
                    </div>
                  </section>
                )}

                {/* Why It Matches */}
                {ranking?.match_explanation && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Lightbulb className="w-4 h-4 text-yellow-500" />
                      Why This Matches You
                    </h3>
                    <p className="text-sm text-muted-foreground leading-relaxed bg-muted/40 rounded-xl p-3">
                      {ranking.match_explanation}
                    </p>
                  </section>
                )}

                {/* Strengths & Gaps */}
                {ranking && (ranking.strengths.length > 0 || ranking.gaps.length > 0) && (
                  <section>
                    <div className="grid grid-cols-2 gap-3">
                      {ranking.strengths.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase tracking-wider mb-2">
                            Strengths
                          </h4>
                          <ul className="space-y-1">
                            {ranking.strengths.map((s, i) => (
                              <li
                                key={i}
                                className="flex items-start gap-1.5 text-xs text-muted-foreground"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                                {s}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {ranking.gaps.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-yellow-600 dark:text-yellow-400 uppercase tracking-wider mb-2">
                            Gaps
                          </h4>
                          <ul className="space-y-1">
                            {ranking.gaps.map((g, i) => (
                              <li
                                key={i}
                                className="flex items-start gap-1.5 text-xs text-muted-foreground"
                              >
                                <AlertCircle className="w-3.5 h-3.5 text-yellow-500 mt-0.5 shrink-0" />
                                {g}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    {ranking.suggestions.length > 0 && (
                      <div className="mt-3">
                        <h4 className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-2">
                          Suggestions
                        </h4>
                        <ul className="space-y-1">
                          {ranking.suggestions.map((s, i) => (
                            <li
                              key={i}
                              className="flex items-start gap-1.5 text-xs text-muted-foreground"
                            >
                              <Lightbulb className="w-3.5 h-3.5 text-blue-500 mt-0.5 shrink-0" />
                              {s}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </section>
                )}

                {/* Contacts */}
                {contacts.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Mail className="w-4 h-4 text-primary" />
                      Contacts ({contacts.length})
                    </h3>
                    <div className="bg-muted/30 rounded-xl p-3">
                      {contacts.map((contact, i) => (
                        <ContactRow key={contact.email ?? i} contact={contact} />
                      ))}
                    </div>
                  </section>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 pt-5 border-t border-border">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3">
                Agent Actions
              </p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => onHandoff(company.id, "email-writer")}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  Generate Cold Email
                </button>
                <button
                  onClick={() => onHandoff(company.id, "resume-tailor")}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-secondary text-secondary-foreground text-sm font-medium hover:bg-secondary/90 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  Tailor Resume
                </button>
                <button
                  onClick={() => onHandoff(company.id, "personalizer")}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl border border-border text-sm font-medium hover:bg-muted transition-colors"
                >
                  <Sparkles className="w-4 h-4" />
                  Personalize
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
