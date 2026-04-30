"use client";

import { motion, useInView } from "framer-motion";
import { useRef, useState } from "react";
import { Search, Sparkles, Mail, CheckCircle, ArrowRight, Play } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: Search,
    title: "Find",
    description: "Our discovery agent scans job boards, company sites, and networks to find opportunities matching your profile.",
    details: [
      "AI-powered job matching",
      "Company culture analysis",
      "Real-time opportunity alerts",
    ],
  },
  {
    number: "02",
    icon: Sparkles,
    title: "Personalize",
    description: "Each outreach is crafted using company research, recent news, and your unique background.",
    details: [
      "Deep company research",
      "Tailored messaging",
      "Resume customization",
    ],
  },
  {
    number: "03",
    icon: Mail,
    title: "Connect",
    description: "Smart email campaigns reach the right people at the right time with your approval.",
    details: [
      "Human-in-the-loop approval",
      "Optimal send timing",
      "Follow-up automation",
    ],
  },
  {
    number: "04",
    icon: CheckCircle,
    title: "Land",
    description: "Track responses, manage your pipeline, and convert opportunities into offers.",
    details: [
      "Response tracking",
      "Pipeline management",
      "Interview preparation",
    ],
  },
];

export function HowItWorksSection() {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  const [activeStep, setActiveStep] = useState(0);

  return (
    <section ref={ref} className="relative py-24 lg:py-32 overflow-hidden">
      {/* Background accent */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1/3 h-1/2 bg-gradient-to-r from-primary/5 to-transparent blur-3xl" />
        <div className="absolute right-0 top-1/3 w-1/4 h-1/3 bg-gradient-to-l from-secondary/5 to-transparent blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4 text-balance">
            <span className="text-foreground">How It </span>
            <span className="text-gradient">Works</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto text-pretty">
            A streamlined process from discovery to offer, powered by intelligent automation
          </p>
        </motion.div>

        {/* Steps - Desktop */}
        <div className="hidden lg:block">
          {/* Progress line */}
          <div className="relative mb-8">
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-border -translate-y-1/2" />
            <motion.div
              initial={{ width: 0 }}
              animate={isInView ? { width: `${((activeStep + 1) / steps.length) * 100}%` } : {}}
              transition={{ duration: 0.5, delay: 0.5 }}
              className="absolute top-1/2 left-0 h-0.5 bg-gradient-to-r from-primary to-secondary -translate-y-1/2"
            />

            {/* Step indicators */}
            <div className="relative flex justify-between">
              {steps.map((step, i) => {
                const Icon = step.icon;
                const isActive = i <= activeStep;
                return (
                  <motion.button
                    key={step.number}
                    onClick={() => setActiveStep(i)}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={isInView ? { opacity: 1, scale: 1 } : {}}
                    transition={{ delay: 0.3 + i * 0.1 }}
                    whileHover={{ scale: 1.1 }}
                    className="relative group"
                  >
                    <motion.div
                      animate={{
                        scale: i === activeStep ? 1.1 : 1,
                        borderColor: isActive ? "rgb(var(--primary))" : "rgb(var(--border))",
                      }}
                      className={`w-16 h-16 rounded-2xl border-2 flex items-center justify-center transition-colors ${
                        isActive
                          ? "bg-gradient-to-br from-primary to-secondary"
                          : "bg-card"
                      }`}
                    >
                      <Icon
                        className={`w-7 h-7 ${
                          isActive ? "text-primary-foreground" : "text-muted-foreground"
                        }`}
                      />
                    </motion.div>
                    <span
                      className={`absolute -bottom-8 left-1/2 -translate-x-1/2 text-sm font-semibold whitespace-nowrap ${
                        isActive ? "text-primary" : "text-muted-foreground"
                      }`}
                    >
                      {step.title}
                    </span>
                  </motion.button>
                );
              })}
            </div>
          </div>

          {/* Active step content */}
          <motion.div
            key={activeStep}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mt-20"
          >
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <div className="flex items-center gap-4 mb-4">
                  <span className="text-6xl font-bold text-primary/20">
                    {steps[activeStep].number}
                  </span>
                  <h3 className="text-3xl font-bold text-foreground">
                    {steps[activeStep].title}
                  </h3>
                </div>
                <p className="text-lg text-muted-foreground mb-6">
                  {steps[activeStep].description}
                </p>
                <ul className="space-y-3">
                  {steps[activeStep].details.map((detail, i) => (
                    <motion.li
                      key={detail}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className="flex items-center gap-3"
                    >
                      <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                        <CheckCircle className="w-4 h-4 text-primary" />
                      </div>
                      <span className="text-foreground">{detail}</span>
                    </motion.li>
                  ))}
                </ul>

                {activeStep < steps.length - 1 && (
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setActiveStep(activeStep + 1)}
                    className="mt-8 flex items-center gap-2 px-6 py-3 rounded-xl bg-primary/10 text-primary font-medium hover:bg-primary/20 transition-colors"
                  >
                    Next Step
                    <ArrowRight className="w-4 h-4" />
                  </motion.button>
                )}
              </div>

              {/* Visual */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="relative aspect-square max-w-md mx-auto"
              >
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-primary/20 to-secondary/20 blur-2xl" />
                <div className="relative h-full rounded-3xl glass border border-border p-8 flex items-center justify-center overflow-hidden">
                  {/* Animated icon */}
                  <motion.div
                    animate={{
                      scale: [1, 1.1, 1],
                      rotate: [0, 5, -5, 0],
                    }}
                    transition={{ duration: 4, repeat: Infinity }}
                    className="relative"
                  >
                    {(() => {
                      const Icon = steps[activeStep].icon;
                      return (
                        <div className="w-32 h-32 rounded-3xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-xl shadow-primary/30">
                          <Icon className="w-16 h-16 text-primary-foreground" />
                        </div>
                      );
                    })()}

                    {/* Orbiting elements */}
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                      className="absolute inset-[-40px]"
                    >
                      <div className="absolute top-0 left-1/2 w-3 h-3 rounded-full bg-accent" />
                    </motion.div>
                    <motion.div
                      animate={{ rotate: -360 }}
                      transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                      className="absolute inset-[-60px]"
                    >
                      <div className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-secondary" />
                    </motion.div>
                  </motion.div>

                  {/* Scan line effect */}
                  <div className="absolute inset-0 scan-line overflow-hidden rounded-3xl" />
                </div>
              </motion.div>
            </div>
          </motion.div>
        </div>

        {/* Steps - Mobile */}
        <div className="lg:hidden space-y-6">
          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.number}
                initial={{ opacity: 0, x: -30 }}
                animate={isInView ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: 0.2 + i * 0.1 }}
                className="glass border border-border rounded-2xl p-6"
              >
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center flex-shrink-0">
                    <Icon className="w-7 h-7 text-primary-foreground" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono text-muted-foreground">
                        {step.number}
                      </span>
                      <h3 className="text-xl font-bold text-foreground">
                        {step.title}
                      </h3>
                    </div>
                    <p className="text-muted-foreground mb-4">{step.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {step.details.map((detail) => (
                        <span
                          key={detail}
                          className="text-xs px-3 py-1 rounded-full bg-primary/10 text-primary"
                        >
                          {detail}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
