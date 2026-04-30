"use client";

import { motion } from "framer-motion";
import { OrchestrationStep } from "@/lib/types";

const steps: OrchestrationStep[] = [
  {
    id: "CompanyFinder",
    label: "Company Finder",
    description: "Discovers relevant companies",
    status: "completed",
  },
  {
    id: "Personalization",
    label: "Personalization",
    description: "Extracts company insights",
    status: "completed",
  },
  {
    id: "EmailWriter",
    label: "Email Writer",
    description: "Generates outreach emails",
    status: "active",
  },
  {
    id: "Review",
    label: "Human Review",
    description: "User approves emails",
    status: "pending",
  },
  {
    id: "Sender",
    label: "Email Sender",
    description: "Sends via Gmail API",
    status: "pending",
  },
];

const statusStyles = {
  completed: {
    node: "bg-primary/20 border-primary text-primary",
    glow: "shadow-primary/30",
    connector: "bg-primary/50",
    label: "text-primary",
  },
  active: {
    node: "bg-emerald-500/20 border-emerald-500 text-emerald-500",
    glow: "shadow-emerald-500/30",
    connector: "bg-border",
    label: "text-emerald-500",
  },
  pending: {
    node: "bg-muted border-border text-muted-foreground",
    glow: "",
    connector: "bg-border",
    label: "text-muted-foreground",
  },
};

interface OrchestrationFlowProps {
  activeStep?: string;
  currentTask?: string;
}

export default function OrchestrationFlow({
  activeStep,
  currentTask,
}: OrchestrationFlowProps) {
  const resolvedSteps = steps.map((step) => ({
    ...step,
    status: activeStep
      ? step.id === activeStep
        ? "active"
        : steps.findIndex((s) => s.id === activeStep) >
          steps.findIndex((s) => s.id === step.id)
        ? "completed"
        : "pending"
      : step.status,
  })) as OrchestrationStep[];

  return (
    <div className="w-full">
      {/* Flow diagram */}
      <div className="flex items-center justify-between gap-2 overflow-x-auto pb-2">
        {resolvedSteps.map((step, index) => {
          const styles = statusStyles[step.status];
          const isActive = step.status === "active";

          return (
            <div key={step.id} className="flex items-center gap-2 flex-1 min-w-0">
              {/* Node */}
              <div className="flex flex-col items-center gap-2 flex-1">
                <motion.div
                  animate={
                    isActive
                      ? {
                          boxShadow: [
                            "0 0 10px rgba(16,185,129,0.3)",
                            "0 0 20px rgba(16,185,129,0.6)",
                            "0 0 10px rgba(16,185,129,0.3)",
                          ],
                        }
                      : {}
                  }
                  transition={{ duration: 2, repeat: Infinity }}
                  className={`w-12 h-12 rounded-xl border-2 flex items-center justify-center text-lg shadow-lg ${styles.node} ${styles.glow}`}
                >
                  {step.status === "completed" ? "✓" : step.status === "active" ? "⟳" : "○"}
                </motion.div>

                <div className="text-center">
                  <div className={`text-xs font-semibold ${styles.label} whitespace-nowrap`}>
                    {step.label}
                  </div>
                  <div className="text-xs text-muted-foreground whitespace-nowrap hidden sm:block">
                    {step.description}
                  </div>
                </div>

                {isActive && currentTask && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-xs text-emerald-500 text-center max-w-[120px] truncate bg-emerald-500/10 px-2 py-1 rounded-lg border border-emerald-500/20"
                  >
                    {currentTask}
                  </motion.div>
                )}
              </div>

              {/* Connector arrow */}
              {index < resolvedSteps.length - 1 && (
                <div className="flex items-center flex-shrink-0 mb-8">
                  <div className="relative w-8 h-0.5">
                    <div className={`absolute inset-0 ${styles.connector} rounded-full`} />
                    {/* Animated particle for active connector */}
                    {resolvedSteps[index].status === "completed" && (
                      <motion.div
                        className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-primary"
                        animate={{ x: [0, 28, 0] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      />
                    )}
                  </div>
                  <div className="w-0 h-0 border-t-4 border-t-transparent border-b-4 border-b-transparent border-l-4 border-l-border flex-shrink-0" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
