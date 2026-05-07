"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Bot,
  Globe,
  Code2,
  BarChart2,
  Puzzle,
  DollarSign,
  Loader2,
} from "lucide-react";
import { UserPreferences } from "@/lib/types";
import { saveUserPreferences } from "@/lib/api";

// â”€â”€â”€ Inline LinkedIn SVG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const LinkedinIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
);

const TwitterIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

const GithubIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
  </svg>
);

// â”€â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

type SelectionAnswer = { type: "multi" | "single"; values: string[] };
type LinksAnswer = { type: "links"; values: Record<string, string> };
type TextAnswer = { type: "text"; value: string };
type SalaryAnswer = { type: "salary"; min: number | null; max: number | null };
type PriorityAnswer = { type: "priorities"; values: Record<string, number> };
type Answer = SelectionAnswer | LinksAnswer | TextAnswer | SalaryAnswer | PriorityAnswer;

interface Step {
  id: string;
  question: string;
  subtitle?: string;
  type: "single" | "multi" | "links" | "text" | "salary" | "priorities";
  options?: string[];
  linkFields?: { key: string; label: string; icon: React.ElementType; placeholder: string }[];
  priorityFields?: string[];
  allowOther?: boolean;
  required?: boolean;
}

// â”€â”€â”€ Steps Definition â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const STEPS: Step[] = [
  {
    id: "preferred_roles",
    question: "What types of roles are you targeting?",
    subtitle: "Select all that apply",
    type: "multi",
    options: [
      "Software Engineer", "Frontend Engineer", "Backend Engineer",
      "Full Stack Engineer", "ML / AI Engineer", "Data Scientist",
      "Data Engineer", "DevOps / Platform Engineer", "Product Manager",
      "Research Scientist", "Mobile Engineer", "Security Engineer",
    ],
    allowOther: true,
    required: true,
  },
  {
    id: "work_mode",
    question: "What's your preferred work arrangement?",
    type: "single",
    options: ["Remote", "Hybrid", "Onsite", "Flexible (any)"],
    required: true,
  },
  {
    id: "preferred_locations",
    question: "Which locations are you open to?",
    subtitle: "Select all that apply (or add your own)",
    type: "multi",
    options: [
      "San Francisco Bay Area", "New York City", "Seattle", "Austin",
      "Boston", "Los Angeles", "Chicago", "Remote (anywhere)", "Outside US",
    ],
    allowOther: true,
  },
  {
    id: "employment_type",
    question: "What type of employment are you looking for?",
    type: "multi",
    options: ["Full-time", "Internship", "Part-time", "Contract / Freelance"],
    required: true,
  },
  {
    id: "salary",
    question: "What's your salary expectation?",
    subtitle: "Annual base salary (USD). Leave blank to skip.",
    type: "salary",
  },
  {
    id: "company_size",
    question: "What company sizes interest you?",
    subtitle: "Select all that apply",
    type: "multi",
    options: [
      "Startup (< 50)", "Small (50-200)", "Mid-size (200-1000)",
      "Large (1000-5000)", "Enterprise (5000+)",
    ],
    allowOther: false,
  },
  {
    id: "industries",
    question: "Which industries excite you most?",
    subtitle: "Select up to 5",
    type: "multi",
    options: [
      "AI / ML", "Fintech", "Healthcare / Biotech", "Developer Tools",
      "Cybersecurity", "Climate / Cleantech", "E-commerce", "EdTech",
      "Gaming", "Enterprise SaaS", "Consumer Apps", "Crypto / Web3",
    ],
    allowOther: true,
  },
  {
    id: "open_to_startups",
    question: "Are you open to early-stage startups (seed / Series A)?",
    type: "single",
    options: ["Yes, love them", "Maybe â€” depends on the team", "No, prefer established companies"],
  },
  {
    id: "sponsorship",
    question: "Do you require visa sponsorship?",
    type: "single",
    options: ["Yes â€” I need sponsorship", "No â€” I don't need sponsorship", "Not sure yet"],
    required: true,
  },
  {
    id: "start_date",
    question: "When can you start?",
    type: "single",
    options: ["Immediately", "Within 1 month", "1-3 months", "3-6 months", "6+ months"],
    required: true,
  },
  {
    id: "career_priorities",
    question: "Rank what matters most to you (1 = not important, 5 = very important)",
    type: "priorities",
    priorityFields: ["Compensation", "Learning & Growth", "Company Brand", "Work-Life Balance", "Research / Innovation", "Impact"],
    required: true,
  },
  {
    id: "avoided",
    question: "Any companies or industries you want to avoid?",
    subtitle: "Optional - type companies or industries separated by commas",
    type: "text",
  },
  {
    id: "profile_links",
    question: "Share your profile links",
    subtitle: "Helps personalize company matches and cold emails. All optional.",
    type: "links",
    linkFields: [
      { key: "linkedin", label: "LinkedIn", icon: LinkedinIcon, placeholder: "linkedin.com/in/yourname" },
      { key: "github", label: "GitHub", icon: GithubIcon, placeholder: "github.com/yourhandle" },
      { key: "portfolio", label: "Portfolio", icon: Globe, placeholder: "yoursite.com" },
      { key: "twitter", label: "Twitter / X", icon: TwitterIcon, placeholder: "twitter.com/yourhandle" },
      { key: "devpost", label: "Devpost", icon: Code2, placeholder: "devpost.com/yourhandle" },
      { key: "kaggle", label: "Kaggle", icon: BarChart2, placeholder: "kaggle.com/yourhandle" },
      { key: "leetcode", label: "LeetCode", icon: Puzzle, placeholder: "leetcode.com/yourhandle" },
    ],
  },
  {
    id: "anything_else",
    question: "Anything else you'd like the AI to know?",
    subtitle: "Tell us anything that would help find the right companies â€” niche interests, deal-breakers, personal goals, etc.",
    type: "text",
  },
];

// â”€â”€â”€ Sub-components â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function OptionButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all ${
        selected
          ? "bg-primary/15 border-primary text-primary"
          : "bg-muted border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
      }`}
    >
      {selected && <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />}
      {label}
    </motion.button>
  );
}

function PrioritySlider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const colors = ["", "bg-red-400", "bg-orange-400", "bg-yellow-400", "bg-blue-500", "bg-green-500"];
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground w-40 shrink-0">{label}</span>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={`w-8 h-8 rounded-lg border text-xs font-bold transition-all ${
              n <= value
                ? `${colors[n]} border-transparent text-white`
                : "bg-muted border-border text-muted-foreground hover:border-primary/40"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <span className="text-xs text-muted-foreground w-20">
        {value === 0 ? "â€”" : value === 5 ? "Essential" : value >= 4 ? "Important" : value >= 3 ? "Moderate" : "Low"}
      </span>
    </div>
  );
}

// â”€â”€â”€ Main Wizard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface PreferenceWizardProps {
  userId: string;
  initialMessage: string;
  initialHistory?: unknown[];
  currentPrefs?: Partial<UserPreferences>;
  onComplete: (preferences: UserPreferences) => void;
}

function mapPrefsToAnswers(currentPrefs?: Partial<UserPreferences>): Record<string, Answer> {
  if (!currentPrefs) return {};

  const answers: Record<string, Answer> = {};
  const stepOption = (stepId: string, matcher: (value: string) => boolean, fallback: string) => {
    const step = STEPS.find((s) => s.id === stepId);
    return step?.options?.find(matcher) ?? fallback;
  };

  const workModeMap: Record<string, string> = {
    remote: "Remote",
    hybrid: "Hybrid",
    onsite: "Onsite",
    flexible: "Flexible (any)",
  };

  const employmentTypeMap: Record<string, string> = {
    full_time: "Full-time",
    internship: "Internship",
    part_time: "Part-time",
    contract: "Contract / Freelance",
    freelance: "Contract / Freelance",
  };

  const companySizeMap: Record<string, string> = {
    "startup (<50)": "Startup (< 50)",
    "startup (< 50)": "Startup (< 50)",
    "small (50-200)": "Small (50-200)",
    "mid (200-1000)": "Mid-size (200-1000)",
    "mid-size (200-1000)": "Mid-size (200-1000)",
    "large (1000-5000)": "Large (1000-5000)",
    "enterprise (5000+)": "Enterprise (5000+)",
  };

  if (currentPrefs.preferred_roles?.length) {
    answers.preferred_roles = { type: "multi", values: currentPrefs.preferred_roles };
  }

  if (currentPrefs.work_mode) {
    answers.work_mode = {
      type: "single",
      values: [workModeMap[currentPrefs.work_mode] ?? "Flexible (any)"],
    };
  }

  if (currentPrefs.preferred_locations?.length) {
    answers.preferred_locations = {
      type: "multi",
      values: currentPrefs.preferred_locations,
    };
  }

  if (currentPrefs.employment_type?.length) {
    answers.employment_type = {
      type: "multi",
      values: currentPrefs.employment_type.map((value) => employmentTypeMap[value] ?? value),
    };
  }

  if (typeof currentPrefs.salary_min === "number" || typeof currentPrefs.salary_max === "number") {
    answers.salary = {
      type: "salary",
      min: currentPrefs.salary_min ?? null,
      max: currentPrefs.salary_max ?? null,
    };
  }

  if (currentPrefs.company_size_pref?.length) {
    answers.company_size = {
      type: "multi",
      values: currentPrefs.company_size_pref.map((value) => {
        const normalized = value.trim().toLowerCase();
        return companySizeMap[normalized] ?? value;
      }),
    };
  }

  if (currentPrefs.industries_of_interest?.length) {
    answers.industries = {
      type: "multi",
      values: currentPrefs.industries_of_interest,
    };
  }

  if (typeof currentPrefs.open_to_startups === "boolean") {
    answers.open_to_startups = {
      type: "single",
      values: [
        currentPrefs.open_to_startups
          ? stepOption("open_to_startups", (v) => v.startsWith("Yes"), "Yes, love them")
          : stepOption("open_to_startups", (v) => v.startsWith("No"), "No, prefer established companies"),
      ],
    };
  }

  if (typeof currentPrefs.sponsorship_required === "boolean") {
    answers.sponsorship = {
      type: "single",
      values: [
        currentPrefs.sponsorship_required
          ? stepOption("sponsorship", (v) => v.startsWith("Yes"), "Yes")
          : stepOption("sponsorship", (v) => v.startsWith("No"), "No"),
      ],
    };
  }

  if (currentPrefs.earliest_start) {
    answers.start_date = {
      type: "single",
      values: [currentPrefs.earliest_start],
    };
  }

  if (currentPrefs.career_priorities && Object.keys(currentPrefs.career_priorities).length > 0) {
    const reversePriorityMap: Record<string, string> = {
      compensation: "Compensation",
      learning: "Learning & Growth",
      brand_value: "Company Brand",
      work_life_balance: "Work-Life Balance",
      research: "Research / Innovation",
      growth: "Impact",
    };
    const values: Record<string, number> = {};
    Object.entries(currentPrefs.career_priorities).forEach(([k, v]) => {
      const mapped = reversePriorityMap[k] ?? k;
      values[mapped] = Number(v);
    });
    answers.career_priorities = { type: "priorities", values };
  }

  const avoidedParts = [
    ...(currentPrefs.avoided_companies ?? []),
    ...(currentPrefs.avoided_industries ?? []),
  ];
  if (avoidedParts.length) {
    answers.avoided = { type: "text", value: avoidedParts.join(", ") };
  }

  if (currentPrefs.profile_links && Object.keys(currentPrefs.profile_links).length > 0) {
    answers.profile_links = { type: "links", values: currentPrefs.profile_links };
  }

  const notes = (currentPrefs as Partial<UserPreferences> & { notes?: string }).notes;
  if (notes) {
    answers.anything_else = { type: "text", value: notes };
  }

  return answers;
}

export default function PreferenceWizard({
  userId,
  initialMessage,
  currentPrefs,
  onComplete,
}: PreferenceWizardProps) {
  const [stepIndex, setStepIndex] = useState(-1); // -1 = greeting
  const [answers, setAnswers] = useState<Record<string, Answer>>(() => mapPrefsToAnswers(currentPrefs));
  const [otherInputs, setOtherInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const step = stepIndex >= 0 ? STEPS[stepIndex] : null;
  const isLast = stepIndex === STEPS.length - 1;
  const progress = stepIndex < 0 ? 0 : Math.round(((stepIndex + 1) / STEPS.length) * 100);

  // â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  function getSelectionValues(id: string): string[] {
    const a = answers[id];
    if (!a || a.type === "links" || a.type === "salary" || a.type === "priorities" || a.type === "text") return [];
    return a.values;
  }

  function toggleOption(id: string, option: string, multi: boolean) {
    const current = getSelectionValues(id);
    let next: string[];
    if (multi) {
      next = current.includes(option)
        ? current.filter((v) => v !== option)
        : [...current, option];
    } else {
      next = current.includes(option) ? [] : [option];
    }
    setAnswers((prev) => ({ ...prev, [id]: { type: multi ? "multi" : "single", values: next } }));
  }

  function setLinks(id: string, key: string, value: string) {
    const a = answers[id];
    const existing = a?.type === "links" ? a.values : {};
    setAnswers((prev) => ({
      ...prev,
      [id]: { type: "links", values: { ...existing, [key]: value } },
    }));
  }

  function getLinks(id: string): Record<string, string> {
    const a = answers[id];
    return a?.type === "links" ? a.values : {};
  }

  function getSalary(id: string): { min: number | null; max: number | null } {
    const a = answers[id];
    return a?.type === "salary" ? { min: a.min, max: a.max } : { min: null, max: null };
  }

  function getPriorities(id: string): Record<string, number> {
    const a = answers[id];
    return a?.type === "priorities" ? a.values : {};
  }

  function getText(id: string): string {
    const a = answers[id];
    return a?.type === "text" ? a.value : "";
  }

  function addOther(id: string) {
    const val = (otherInputs[id] || "").trim();
    if (!val) return;
    const current = getSelectionValues(id);
    if (!current.includes(val)) {
      setAnswers((prev) => ({
        ...prev,
        [id]: { type: "multi", values: [...current, val] },
      }));
    }
    setOtherInputs((prev) => ({ ...prev, [id]: "" }));
  }

  // â”€â”€ Build final preferences â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  function buildPreferences(): UserPreferences {
    const roles = [
      ...getSelectionValues("preferred_roles").filter((v) => v !== "Other"),
    ];

    const workModeMap: Record<string, UserPreferences["work_mode"]> = {
      "Remote": "remote",
      "Hybrid": "hybrid",
      "Onsite": "onsite",
      "Flexible (any)": "flexible",
    };
    const workModeRaw = getSelectionValues("work_mode")[0] ?? "";

    const locs = getSelectionValues("preferred_locations").filter((v) => v !== "Other");

    const empTypeMap: Record<string, string> = {
      "Full-time": "full_time",
      "Internship": "internship",
      "Part-time": "part_time",
      "Contract / Freelance": "contract",
    };

    const salary = getSalary("salary");

    const companySizeMap: Record<string, string> = {
      "Startup (< 50)": "startup (<50)",
      "Small (50-200)": "small (50-200)",
      "Mid-size (200-1000)": "mid (200-1000)",
      "Large (1000-5000)": "large (1000-5000)",
      "Enterprise (5000+)": "enterprise (5000+)",
    };

    const startupRaw = getSelectionValues("open_to_startups")[0] ?? "";
    const sponsorRaw = getSelectionValues("sponsorship")[0] ?? "";

    const startDateMap: Record<string, string> = {
      "Immediately": "Immediately",
      "Within 1 month": "Within 1 month",
      "1-3 months": "1-3 months",
      "3-6 months": "3-6 months",
      "6+ months": "6+ months",
    };

    const priorityKeys: Record<string, string> = {
      "Compensation": "compensation",
      "Learning & Growth": "learning",
      "Company Brand": "brand_value",
      "Work-Life Balance": "work_life_balance",
      "Research / Innovation": "research",
      "Impact": "growth",
    };
    const rawPriorities = getPriorities("career_priorities");
    const careerPriorities: Record<string, number> = {};
    Object.entries(rawPriorities).forEach(([k, v]) => {
      const mapped = priorityKeys[k];
      if (mapped) careerPriorities[mapped] = v;
    });

    const avoidedRaw = getText("avoided");
    const avoidedParts = avoidedRaw.split(",").map((s) => s.trim()).filter(Boolean);

    const links = getLinks("profile_links");
    const anythingElse = getText("anything_else");

    return {
      user_id: userId,
      preferred_roles: roles,
      preferred_locations: locs,
      work_mode: workModeMap[workModeRaw] ?? "flexible",
      employment_type: getSelectionValues("employment_type").map((v) => empTypeMap[v] ?? v) as UserPreferences["employment_type"],
      salary_min: salary.min ?? undefined,
      salary_max: salary.max ?? undefined,
      open_to_startups: startupRaw.startsWith("Yes"),
      company_size_pref: getSelectionValues("company_size").map((v) => companySizeMap[v] ?? v),
      industries_of_interest: getSelectionValues("industries").filter((v) => v !== "Other"),
      sponsorship_required: sponsorRaw.startsWith("Yes"),
      earliest_start: startDateMap[getSelectionValues("start_date")[0] ?? ""] ?? undefined,
      career_priorities: careerPriorities,
      avoided_companies: avoidedParts.filter((p) => !p.toLowerCase().includes("industry")),
      avoided_industries: avoidedParts.filter((p) => p.toLowerCase().includes("industry")),
      open_to_cold_outreach: true,
      profile_links: links as UserPreferences["profile_links"],
      notes: anythingElse || undefined,
      conversation_complete: true,
    } as unknown as UserPreferences;
  }

  // â”€â”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  async function handleNext() {
    if (isLast) {
      setSaving(true);
      try {
        const prefs = buildPreferences();
        await saveUserPreferences(userId, prefs);
        onComplete(prefs);
      } finally {
        setSaving(false);
      }
    } else {
      setStepIndex((i) => i + 1);
    }
  }

  function handleBack() {
    setStepIndex((i) => Math.max(-1, i - 1));
  }

  // â”€â”€ Can proceed? â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  function canProceed(): boolean {
    if (!step) return true; // greeting
    if (!step.required) return true;
    if (step.type === "single" || step.type === "multi") {
      return getSelectionValues(step.id).length > 0;
    }
    if (step.type === "priorities") {
      const vals = getPriorities(step.id);
      return Object.keys(vals).length > 0;
    }
    return true;
  }

  // â”€â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  return (
    <div className="flex flex-col h-full">
      {/* Progress */}
      <div className="px-5 py-3 border-b border-border">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
          <span>{stepIndex < 0 ? "Getting started" : `Step ${stepIndex + 1} of ${STEPS.length}`}</span>
          <span className="font-medium">{progress}%</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-primary rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <AnimatePresence mode="wait">
          {stepIndex === -1 ? (
            // â”€â”€ Greeting â”€â”€
            <motion.div
              key="greeting"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              className="flex flex-col gap-4"
            >
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0">
                  <Bot className="w-5 h-5" />
                </div>
                <div className="bg-muted text-foreground text-sm leading-relaxed px-4 py-3 rounded-2xl rounded-tl-sm max-w-lg">
                  {initialMessage}
                  <p className="mt-2 text-muted-foreground">
                    I&apos;ll walk you through <strong>{STEPS.length} quick questions</strong> â€” each with options to choose from. It takes about 2 minutes.
                  </p>
                </div>
              </div>
            </motion.div>
          ) : step ? (
            // â”€â”€ Question Step â”€â”€
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -30 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col gap-4"
            >
              <div>
                <h3 className="text-base font-semibold text-foreground">{step.question}</h3>
                {step.subtitle && (
                  <p className="text-xs text-muted-foreground mt-1">{step.subtitle}</p>
                )}
              </div>

              {/* Single / Multi choice */}
              {(step.type === "single" || step.type === "multi") && (
                <div className="flex flex-wrap gap-2">
                  {step.options!.map((opt) => (
                    <OptionButton
                      key={opt}
                      label={opt}
                      selected={getSelectionValues(step.id).includes(opt)}
                      onClick={() => toggleOption(step.id, opt, step.type === "multi")}
                    />
                  ))}
                  {step.allowOther && (
                    <div className="flex gap-2 w-full mt-1">
                      <input
                        type="text"
                        value={otherInputs[step.id] ?? ""}
                        onChange={(e) => setOtherInputs((p) => ({ ...p, [step.id]: e.target.value }))}
                        onKeyDown={(e) => e.key === "Enter" && addOther(step.id)}
                        placeholder="Other â€” type and press Enter"
                        className="flex-1 bg-muted border border-border rounded-xl px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors"
                      />
                      <button
                        type="button"
                        onClick={() => addOther(step.id)}
                        className="px-3 py-2 rounded-xl border border-border text-sm hover:bg-muted transition-colors"
                      >
                        Add
                      </button>
                    </div>
                  )}
                  {/* Show custom "other" values as selected chips */}
                  {step.allowOther && getSelectionValues(step.id)
                    .filter((v) => !step.options!.includes(v))
                    .map((v) => (
                      <OptionButton
                        key={v}
                        label={v}
                        selected
                        onClick={() => toggleOption(step.id, v, true)}
                      />
                    ))}
                </div>
              )}

              {/* Salary */}
              {step.type === "salary" && (
                <div className="flex gap-4 flex-wrap">
                  {(["min", "max"] as const).map((k) => (
                    <div key={k} className="flex flex-col gap-1.5 flex-1 min-w-36">
                      <label className="text-xs text-muted-foreground uppercase tracking-wider">
                        {k === "min" ? "Minimum" : "Maximum"}
                      </label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                          type="number"
                          min={0}
                          step={5000}
                          placeholder={k === "min" ? "e.g. 80000" : "e.g. 150000"}
                          value={getSalary(step.id)[k] ?? ""}
                          onChange={(e) => {
                            const v = e.target.value ? Number(e.target.value) : null;
                            const cur = getSalary(step.id);
                            setAnswers((prev) => ({
                              ...prev,
                              [step.id]: { type: "salary", ...cur, [k]: v },
                            }));
                          }}
                          className="w-full pl-9 pr-3 py-2.5 bg-muted border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Priorities */}
              {step.type === "priorities" && (
                <div className="flex flex-col gap-3">
                  {step.priorityFields!.map((field) => (
                    <PrioritySlider
                      key={field}
                      label={field}
                      value={getPriorities(step.id)[field] ?? 3}
                      onChange={(v) => {
                        const cur = getPriorities(step.id);
                        setAnswers((prev) => ({
                          ...prev,
                          [step.id]: { type: "priorities", values: { ...cur, [field]: v } },
                        }));
                      }}
                    />
                  ))}
                </div>
              )}

              {/* Links */}
              {step.type === "links" && (
                <div className="flex flex-col gap-3">
                  {step.linkFields!.map(({ key, label, icon: Icon, placeholder }) => (
                    <div key={key} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-muted border border-border flex items-center justify-center shrink-0 text-muted-foreground">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1">
                        <label className="text-xs text-muted-foreground mb-1 block">{label}</label>
                        <input
                          type="url"
                          value={getLinks(step.id)[key] ?? ""}
                          onChange={(e) => setLinks(step.id, key, e.target.value)}
                          placeholder={placeholder}
                          className="w-full px-3 py-2 bg-muted border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Free text */}
              {step.type === "text" && (
                <textarea
                  rows={4}
                  value={getText(step.id)}
                  onChange={(e) =>
                    setAnswers((prev) => ({
                      ...prev,
                      [step.id]: { type: "text", value: e.target.value },
                    }))
                  }
                  placeholder="Type here..."
                  className="w-full px-4 py-3 bg-muted border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none transition-colors resize-none"
                />
              )}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {/* Navigation footer */}
      <div className="px-5 py-4 border-t border-border flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={handleBack}
          disabled={stepIndex === -1}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-30 transition-all"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {step && !step.required && (
            <span className="opacity-60">Optional â€” you can skip</span>
          )}
        </div>

        <button
          type="button"
          onClick={handleNext}
          disabled={!canProceed() || saving}
          className="flex items-center gap-2 px-5 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-40 transition-all"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : isLast ? (
            <>
              <CheckCircle2 className="w-4 h-4" />
              Find Companies
            </>
          ) : stepIndex === -1 ? (
            <>
              Get Started
              <ChevronRight className="w-4 h-4" />
            </>
          ) : (
            <>
              Next
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
