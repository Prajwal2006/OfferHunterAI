"use client";

import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import {
  Search,
  Sparkles,
  Mail,
  Target,
  Shield,
  Zap,
  Bot,
  TrendingUp,
} from "lucide-react";

const features = [
  {
    icon: Search,
    title: "Intelligent Discovery",
    description:
      "AI agents continuously scan thousands of opportunities, filtering for your perfect match based on skills, culture, and growth potential.",
    gradient: "from-cyan-500 to-blue-500",
    delay: 0,
  },
  {
    icon: Sparkles,
    title: "Hyper-Personalization",
    description:
      "Every outreach is uniquely crafted using company research, recent news, and your personal story for maximum impact.",
    gradient: "from-blue-500 to-purple-500",
    delay: 0.1,
  },
  {
    icon: Mail,
    title: "Smart Outreach",
    description:
      "Automated email campaigns with human oversight. Review, approve, and track every message before it goes out.",
    gradient: "from-purple-500 to-pink-500",
    delay: 0.2,
  },
  {
    icon: Target,
    title: "Pipeline Management",
    description:
      "Track every opportunity through your personal pipeline with real-time status updates and follow-up reminders.",
    gradient: "from-pink-500 to-rose-500",
    delay: 0.3,
  },
  {
    icon: Shield,
    title: "Human-in-the-Loop",
    description:
      "You stay in control. AI suggests, you decide. Every action requires your approval before execution.",
    gradient: "from-rose-500 to-orange-500",
    delay: 0.4,
  },
  {
    icon: TrendingUp,
    title: "Analytics Dashboard",
    description:
      "Deep insights into your outreach performance, response rates, and optimization suggestions.",
    gradient: "from-orange-500 to-amber-500",
    delay: 0.5,
  },
];

export function FeaturesSection() {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <section ref={ref} className="relative py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={isInView ? { opacity: 1, scale: 1 } : {}}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-secondary/30 mb-6"
          >
            <Bot className="w-4 h-4 text-secondary" />
            <span className="text-sm font-medium">Powered by AI Agents</span>
          </motion.div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-4 text-balance">
            <span className="text-foreground">A Complete System for</span>
            <br />
            <span className="text-gradient">Modern Job Hunting</span>
          </h2>

          <p className="text-lg text-muted-foreground max-w-2xl mx-auto text-pretty">
            Our multi-agent architecture handles every step of the job search process,
            from discovery to landing offers.
          </p>
        </motion.div>

        {/* Features grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 30 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: feature.delay + 0.3, duration: 0.5 }}
              >
                <motion.div
                  whileHover={{ y: -8, scale: 1.02 }}
                  transition={{ type: "spring", stiffness: 400 }}
                  className="group h-full p-6 rounded-2xl glass border border-border hover:border-primary/30 card-hover relative overflow-hidden"
                >
                  {/* Gradient background on hover */}
                  <div
                    className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-500`}
                  />

                  {/* Animated corner accent */}
                  <div className="absolute top-0 right-0 w-20 h-20 overflow-hidden">
                    <motion.div
                      initial={{ x: 30, y: -30, rotate: 45 }}
                      whileHover={{ x: 0, y: 0 }}
                      className={`w-full h-full bg-gradient-to-br ${feature.gradient} opacity-10`}
                    />
                  </div>

                  <div className="relative z-10">
                    {/* Icon */}
                    <motion.div
                      whileHover={{ scale: 1.1, rotate: 5 }}
                      className={`w-14 h-14 rounded-xl bg-gradient-to-br ${feature.gradient} p-[1px] mb-5`}
                    >
                      <div className="w-full h-full rounded-xl bg-card flex items-center justify-center">
                        <Icon className={`w-6 h-6 bg-gradient-to-br ${feature.gradient} [&>*]:fill-current text-transparent bg-clip-text`} 
                          style={{ 
                            color: i % 2 === 0 ? 'rgb(var(--primary))' : 'rgb(var(--secondary))'
                          }}
                        />
                      </div>
                    </motion.div>

                    {/* Content */}
                    <h3 className="text-xl font-semibold mb-3 text-foreground group-hover:text-primary transition-colors">
                      {feature.title}
                    </h3>
                    <p className="text-muted-foreground leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </motion.div>
              </motion.div>
            );
          })}
        </div>

        {/* Bottom CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 1, duration: 0.5 }}
          className="flex justify-center mt-12"
        >
          <motion.div
            whileHover={{ scale: 1.02 }}
            className="flex items-center gap-3 px-6 py-3 rounded-full glass border border-border"
          >
            <Zap className="w-5 h-5 text-primary" />
            <span className="text-muted-foreground">
              All agents work together seamlessly
            </span>
            <div className="flex -space-x-2">
              {[Bot, Search, Mail].map((AgentIcon, i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0 }}
                  animate={isInView ? { scale: 1 } : {}}
                  transition={{ delay: 1.2 + i * 0.1 }}
                  className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center border-2 border-background"
                >
                  <AgentIcon className="w-4 h-4 text-primary-foreground" />
                </motion.div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
